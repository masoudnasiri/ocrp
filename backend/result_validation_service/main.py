# result_validation_service/main.py
import pika
import json
import pandas as pd

def calculate_check_digit(container_code):
    letter_values = {
        'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17, 'H': 18, 'I': 19, 'J': 20,
        'K': 21, 'L': 23, 'M': 24, 'N': 25, 'O': 26, 'P': 27, 'Q': 28, 'R': 29, 'S': 30, 'T': 31,
        'U': 32, 'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38
    }

    values = []
    for char in container_code:
        if char.isalpha():
            values.append(letter_values[char.upper()])
        else:
            values.append(int(char))

    total = sum(val * (2 ** i) for i, val in enumerate(values))
    check_digit = total % 11
    if check_digit == 10:
        check_digit = 0

    return check_digit

def validate_container_number(container_number):
    if len(container_number) != 11:
        return False

    container_code = container_number[:-1]
    expected_check_digit = int(container_number[-1])
    calculated_check_digit = calculate_check_digit(container_code)

    return expected_check_digit == calculated_check_digit

def validate_iso_type(iso_type, iso_types_df):
    return iso_type in iso_types_df['code'].values

def validate_results(results, iso_types_df):
    container_number = results['text'] # Assuming the extracted text is the container number
    iso_type = results['text'] # Assuming the extracted text is the ISO type

    container_valid = validate_container_number(container_number)
    iso_type_valid = validate_iso_type(iso_type, iso_types_df)

    return container_valid and iso_type_valid

def main():
    print("Result Validation Service started.")

    try:
        # Load ISO types CSV (simulate for now)
        iso_types_data = {'code': ['22B0', '22B1', '22B3']}
        iso_types_df = pd.DataFrame(iso_types_data)

        # RabbitMQ connection
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='ocr_results')
        channel.queue_declare(queue='validated_results')

        def callback(ch, method, properties, body):
            try:
                # Decode OCR results
                ocr_results = json.loads(body)

                validated_results = []
                for result in ocr_results:
                    valid = validate_results(result, iso_types_df)
                    result["valid"] = valid
                    validated_results.append(result)

                # Publish validated results to RabbitMQ
                channel.basic_publish(exchange='', routing_key='validated_results', body=json.dumps(validated_results))
                print("Validated results published.")

            except Exception as e:
                print(f"Error processing OCR results: {e}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='ocr_results', on_message_callback=callback)

        print('Waiting for OCR results. To exit press CTRL+C')
        channel.start_consuming()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()