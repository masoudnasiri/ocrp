import cv2
import pika
import numpy as np
import threading
import time
import logging
import socketio
import eventlet
import os
import base64
import requests
from typing import Optional, Tuple, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Camera Management API URL (Ensure this is correct)
CAMERA_MANAGEMENT_API_URL = "http://127.0.0.1:5001/cameras"

# Create a Socket.IO server
sio = socketio.Server(cors_allowed_origins='*', async_mode='eventlet')
# Wrap the SocketIO server in a WSGI application
app = socketio.WSGIApp(sio, static_files={'/': {'content_type': 'text/html', 'filename': 'index.html'}})  # You might need to adjust static file serving

class CameraThread(threading.Thread):
    def __init__(self, camera_id: str):
        super().__init__()
        self.camera_id = camera_id
        self.running = True
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_frame_time: float = time.time()
        self.frame_interval: float = 0.05  # Target interval (20fps)
        self.rabbitmq_connection: Optional[pika.BlockingConnection] = None
        self.rabbitmq_channel: Optional[pika.BlockingConnection.channel] = None
        self.rtsp_url: Optional[str] = None

    def fetch_camera_url(self) -> bool:
        """Fetches the RTSP URL from the camera management API."""
        try:
            response = requests.get(f"{CAMERA_MANAGEMENT_API_URL}/{self.camera_id}")
            response.raise_for_status()
            camera_data = response.json()
            self.rtsp_url = camera_data.get("ip_address")
            if not self.rtsp_url:
                logging.error(f"Camera URL not found for camera {self.camera_id}")
                return False
            logging.info(f"Fetched camera URL: {self.rtsp_url} for camera {self.camera_id}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching camera URL for {self.camera_id}: {e}")
            return False

    def connect_to_rabbitmq(self) -> None:
        """Connects to RabbitMQ."""
        try:
            self.rabbitmq_connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost'))
            self.rabbitmq_channel = self.rabbitmq_connection.channel()
            self.rabbitmq_channel.queue_declare(queue='video_frames')
            logging.info(f"Connected to RabbitMQ for camera {self.camera_id}")
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}")
            self.running = False

    def open_video_capture(self) -> bool:
        """Opens the video capture."""
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        if not self.rtsp_url:
            logging.error(f"RTSP URL is not available for camera {self.camera_id}")
            return False
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            logging.error(f"Error: Could not open video stream from {self.rtsp_url}")
            return False
        return True

    def run(self) -> None:
        """Main thread loop."""
        if not self.fetch_camera_url():
            return

        if not self.open_video_capture():
            return

        self.connect_to_rabbitmq()
        if not self.rabbitmq_channel:
            return

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    logging.warning(
                        f"No frame received or frame is None from {self.rtsp_url}")
                    time.sleep(0.1)
                    continue

                current_time = time.time()
                time_elapsed = current_time - self.last_frame_time
                time_to_wait = max(0, self.frame_interval - time_elapsed)
                time.sleep(time_to_wait)

                ret_enc, img_encoded = cv2.imencode(
                    '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                if not ret_enc:
                    logging.error(f"Error: Failed to encode frame from {self.rtsp_url}")
                    continue

                img_bytes: bytes = img_encoded.tobytes()
                img_base64: str = base64.b64encode(img_bytes).decode('utf-8')

                try:
                    self.rabbitmq_channel.basic_publish(
                        exchange='', routing_key='video_frames', body=img_bytes)
                    logging.info(f"Frame sent to RabbitMQ from {self.rtsp_url}")
                except pika.exceptions.AMQPConnectionError as e:
                    logging.error(f"Error sending to RabbitMQ: {e}")
                    self.connect_to_rabbitmq()
                    if not self.rabbitmq_channel:
                        continue

                sio.emit('video_feed', {'camera_id': self.camera_id, 'frame': img_base64})
                self.last_frame_time = current_time

        except Exception as e:
            logging.exception(f"An unexpected error occurred in CameraThread: {e}")
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Cleans up resources."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            try:
                self.rabbitmq_connection.close()
            except Exception as e:
                logging.error(f"Error closing RabbitMQ connection: {e}")

    def stop(self) -> None:
        """Stops the thread."""
        self.running = False

def start_camera_stream(camera_id: str) -> CameraThread:
    """Starts a camera stream in a separate thread."""
    logging.info(f"Starting stream for camera {camera_id}")
    camera_thread = CameraThread(camera_id)
    camera_thread.start()
    return camera_thread

def main():
    """Main application entry point."""
    camera_threads: Dict[str, CameraThread] = {}
    try:
        # The corrected way to run the SocketIO server
        eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)
    except KeyboardInterrupt:
        logging.info("Stopping camera streams...")
        for camera_thread in camera_threads.values():
            camera_thread.stop()
            camera_thread.join()
        logging.info("Camera streams stopped.")

@sio.on('connect')
def connect(sid, environ):
    logging.info(f"Client connected: {sid}")

@sio.on('disconnect')
def disconnect(sid):
    logging.info(f"Client disconnected: {sid}")

@sio.on('start_stream')
def handle_start_stream(sid, data):
    """Handles the 'start_stream' event from a client."""
    camera_id = data.get('camera_id')

    if not camera_id:
        logging.warning(f"Received invalid start_stream request from {sid}: {data}")
        sio.emit('stream_error', {'error': 'camera_id is required'}, room=sid)
        return

    logging.info(f"Client {sid} requested to start stream for camera {camera_id}")
    camera_thread = start_camera_stream(camera_id)
    camera_threads[camera_id] = camera_thread

if __name__ == "__main__":
    main()