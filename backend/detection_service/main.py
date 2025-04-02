# detection_service/main.py
import pika
import torch
import cv2
import numpy as np
from ultralytics import YOLO
import json

def main():
    print("Detection Service started.")

    try:
        # Load YOLOv8 model
        model = YOLO("best.pt") # load a pretrained model, replace with your model if needed

        # RabbitMQ connection
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='video_frames')
        channel.queue_declare(queue='detection_results')

        def callback(ch, method, properties, body):
            try:
                # Decode JPEG frame
                img_np = np.frombuffer(body, np.uint8)
                frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                # Perform object detection
                results = model(frame)

                # Extract detection results
                detections = []
                for r in results:
                    for *box, conf, cls in r.xyxy[0]:
                        detections.append({
                            "box": [int(b) for b in box],
                            "confidence": float(conf),
                            "class": int(cls)
                        })

                # Publish detection results to RabbitMQ
                channel.basic_publish(exchange='', routing_key='detection_results', body=json.dumps(detections))
                print("Detection results published.")

            except Exception as e:
                print(f"Error processing frame: {e}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='video_frames', on_message_callback=callback)

        print('Waiting for frames. To exit press CTRL+C')
        channel.start_consuming()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()