import pika
import json

def callback(ch, method, properties, body):
    try:
        detection_results = json.loads(body)
        print(f"Received detection results: {detection_results}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='detection_results')
channel.basic_consume(queue='detection_results', on_message_callback=callback)

print('Waiting for detection results. To exit press CTRL+C')
channel.start_consuming()