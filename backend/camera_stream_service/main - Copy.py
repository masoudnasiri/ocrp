import config
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

# Configure logging (if you haven't already)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a Socket.IO server
sio = socketio.Server(cors_allowed_origins='*', async_mode='eventlet')  # Specify async_mode
app = socketio.WSGIApp(sio)

class CameraThread(threading.Thread):
    def __init__(self, rtsp_url, camera_id):
        threading.Thread.__init__(self)
        self.rtsp_url = rtsp_url
        self.camera_id = camera_id
        self.running = True
        self.cap = None
        self.last_frame_time = time.time()  # Track last frame time
        self.frame_interval = 0.05  # Target interval (20fps)

        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='video_frames')

    def run(self):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        if not self.cap.isOpened():
            logging.error(f"Error: Could not open video stream from {self.rtsp_url}")
            return

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret or frame is None:  # Check for None frame
                    logging.warning(f"No frame received or frame is None from {self.rtsp_url}")
                    time.sleep(0.1)  # Wait a bit before retrying
                    continue

                current_time = time.time()
                time_elapsed = current_time - self.last_frame_time
                time_to_wait = max(0, self.frame_interval - time_elapsed)
                time.sleep(time_to_wait)  # Control frame rate

                ret_enc, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])  # Reduce quality
                if not ret_enc:
                    logging.error(f"Error: Failed to encode frame from {self.rtsp_url}")
                    continue

                img_bytes = img_encoded.tobytes()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                self.channel.basic_publish(exchange='', routing_key='video_frames', body=img_bytes)
                logging.info(f"Frame sent to RabbitMQ from {self.rtsp_url}")

                sio.emit('video_feed', {'camera_id': self.camera_id, 'frame': img_base64})
                self.last_frame_time = time.time()

        except Exception as e:
            logging.exception(f"An unexpected error occurred in CameraThread: {e}")
        finally:
            if self.cap and self.cap.isOpened():
                self.cap.release()
            if self.connection and not self.connection.is_closed:
                self.connection.close()

    def stop(self):
        self.running = False

def main():
    print(f"Camera Stream Service started. Camera URL: {config.CAMERA_URL}")
    camera_thread = CameraThread(config.CAMERA_URL, 'camera1')  # Assign a camera_id
    camera_thread.start()

    try:
        sio.attach(app)
        eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)  # Start the websocket server
    except KeyboardInterrupt:
        print("Stopping camera stream...")
        camera_thread.stop()
        camera_thread.join()
        print("Camera stream stopped.")

if __name__ == "__main__":
    main()