import os
path='/media/dave/james/data/solar/solar5'

import csv

def convert_value(value):
    """Convert a string to int or float if possible, otherwise return as-is"""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value.strip('"')  # Remove quotes if present

data = []
with open(f'{path}/solar5.csv', 'r') as csvfile:
    csvreader = csv.reader(csvfile)
    for row in csvreader:
        # Convert each value in the row
        converted_row = [convert_value(value) for value in row]
        data.append(converted_row)

header='year,month,day,hour,minute,powerUsed,gridIn,solarIn,batteryIn,batteryPer,solarInToday,gridInToday,gridOutToday,updated_timstm'
# Print the first few rows to verify
for row in data:
    filename=f'{path}/solar5_{row[0]}-{row[1]:02d}-{row[2]:02d}.csv'
    if not os.path.exists(filename):
      with open(filename, 'w') as f:
        f.write(f'{header}\n')
    f.close
    with open(filename, "a") as f:
      f.write(f'{",".join(str(x) for x in row)}\n')
    f.close()
