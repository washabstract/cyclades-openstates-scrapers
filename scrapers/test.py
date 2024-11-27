from datetime import date, datetime

def convert_dates_to_strings(data):
    """
    Recursively convert all `date` and `datetime` objects in a dictionary to ISO-format strings.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (date, datetime)):
                data[key] = value.isoformat()
            elif isinstance(value, list):
                data[key] = [convert_dates_to_strings(item) if isinstance(item, (dict, date, datetime)) else item for item in value]
            elif isinstance(value, dict):
                data[key] = convert_dates_to_strings(value)
    return data

test_data = {
    "name": "Open States Test",
    "created_date": datetime(2024, 10, 2).date(),
    "last_modified": datetime(2024, 10, 2, 16, 38, 39),
}
print(test_data)
print(convert_dates_to_strings(test_data))