import pika
import pytesseract
import cv2
import numpy as np
import json
import socketio
import eventlet
import logging
import os
import sys

# Configure logging (if you haven't already)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a Socket.IO server
sio = socketio.Server(cors_allowed_origins='*')
app = socketio.WSGIApp(sio)

def main():
    print("OCR Service started.")

    try:
        # RabbitMQ connection
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='detection_results')
        channel.queue_declare(queue='video_frames')

        def callback(ch, method, properties, body):
            try:
                # Decode detection results
                detections = json.loads(body)

                # Get frame from RabbitMQ video_frames queue
                frame_channel = connection.channel()
                method_frame, properties_frame, frame_body = frame_channel.basic_get(queue='video_frames', auto_ack=True)

                if frame_body:
                    # Decode JPEG frame
                    img_np = np.frombuffer(frame_body, np.uint8)
                    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                    ocr_results = []
                    for detection in detections:
                        box = detection["box"]
                        confidence = detection["confidence"]
                        class_id = detection["class"]

                        # Extract detected region
                        x1, y1, x2, y2 = box
                        roi = frame[y1:y2, x1:x2]

                        # Perform OCR with the trained model
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        tessdata_dir_config = r'--tessdata-dir "' + script_dir + r'"'
                        text = pytesseract.image_to_string(roi, lang='cntr', config=tessdata_dir_config)

                        ocr_result = {
                            "camera_id": "camera1",  # Consistent camera_id
                            "box": box,
                            "confidence": confidence,
                            "class": class_id,
                            "text": text.strip(),
                            "frame": img_base64  # Add base64 frame (if needed for debugging)
                        }
                        ocr_results.append(ocr_result)

                        # Send OCR result to frontend via websocket
                        sio.emit('ocr_results', json.dumps(ocr_results))  # Send array of results

                    logging.info("OCR results published to websocket.")
                else:
                    logging.warning("No frame available for OCR.")

            except Exception as e:
                logging.error(f"Error processing detection results: {e}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='detection_results', on_message_callback=callback)

        print('Waiting for detection results. To exit press CTRL+C')
        eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)

    except Exception as e:
        logging.exception(f"An error occurred in OCR service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()