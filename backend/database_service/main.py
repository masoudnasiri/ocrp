# database_service/main.py
import pika
import json
import psycopg2
import psycopg2.extras

def main():
    print("Database Service started.")

    try:
        # PostgreSQL connection
        conn = psycopg2.connect(
            host="localhost",
            database="container_ocr",
            user="postgres",
            password="Man782761" # Replace with your password
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ocr_results (
                id SERIAL PRIMARY KEY,
                box JSONB,
                confidence FLOAT,
                class_id INTEGER,
                text TEXT,
                valid BOOLEAN
            )
        """)
        conn.commit()

        # RabbitMQ connection
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='validated_results')

        def callback(ch, method, properties, body):
            try:
                # Decode validated results
                validated_results = json.loads(body)

                for result in validated_results:
                    # Insert results into database
                    cur.execute("""
                        INSERT INTO ocr_results (box, confidence, class_id, text, valid)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (json.dumps(result["box"]), result["confidence"], result["class"], result["text"], result["valid"]))

                conn.commit()
                print("Results stored in database.")

            except Exception as e:
                print(f"Error storing results: {e}")
                conn.rollback()

            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='validated_results', on_message_callback=callback)

        print('Waiting for validated results. To exit press CTRL+C')
        channel.start_consuming()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()