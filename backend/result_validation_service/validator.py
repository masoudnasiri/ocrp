# validator.py

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
    container_number = results['container_number']
    iso_type = results['iso_type']

    container_valid = validate_container_number(container_number)
    iso_type_valid = validate_iso_type(iso_type, iso_types_df)

    return container_valid and iso_type_valid