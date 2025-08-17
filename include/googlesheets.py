# Google doings
import gspread  # pip install gspread
# Setting up the authorization
from google.oauth2.service_account import Credentials
from gspread_formatting import cellFormat, numberFormat, format_cell_range
from datetime import datetime
import time
import sys
import re


from include.logger import log

class Spreadsheet:
  def __init__(self, creds_file, spreadsheet_name, worksheet_name):
    scopes = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)
    self.spreadsheet = client.open(spreadsheet_name)
    self.worksheet = self.spreadsheet.worksheet(worksheet_name)


  def convert_types(self,row):
    def try_number(val):
      try:
        return int(val)
      except ValueError:
        try:
          return float(val)
        except ValueError:
          return val
    return [try_number(cell) for cell in row]


  def format_and_fix_numbers(self,worksheet,column_formats):
    def datetime_to_serial(dt):
      """Convert Python datetime to Google Sheets serial number."""
      epoch = datetime(1899, 12, 30)
      delta = dt - epoch
      return delta.days + (delta.seconds / 86400)

    """
    Converts text numbers to actual numbers and applies column formats.
    """
    # Desired formats for each column range

    # 1️⃣ Convert all "number-like" strings into actual numbers
    # Fetch all values as a list of lists
    data = worksheet.get_all_values()

    # Convert cells that are numeric strings into numbers
    cleaned_data = []
    for row in data:
        new_row = []
        for value in row:
        # Try datetime first
          try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            new_row.append(datetime_to_serial(dt))
            continue
          except ValueError:
            pass
          try:
            num = float(value)
            # Keep as int if whole number
            if num.is_integer():
              new_row.append(int(num))
            else:
              new_row.append(num)
            continue
          except ValueError:
            pass

          new_row.append(value)  # leave as-is
        cleaned_data.append(new_row)

    # Update the entire sheet with cleaned values
    if cleaned_data:
        worksheet.update(cleaned_data)

    # 2️⃣ Apply number formats to the specified ranges
    for col_range, num_format in column_formats.items():
        format_cell_range(
            worksheet,
            col_range,
            cellFormat(numberFormat=num_format)
        )

  def get_last_row(self,worksheet):
    """Returns the last non-empty row as a list."""
    values = worksheet.get_all_values()
    if values:
      return self.convert_types(values[-1])
    return []
  
  
  def copy_formulas_for_columns(self, columns):
      """
      Copies formulas from the second-to-last row of each column to the last row,
      adjusting row numbers like Google Sheets drag-down, in ONE API call.
      """
      last_row = len(self.worksheet.get_all_values())
      if last_row < 2:
          raise ValueError("Not enough rows to copy from.")

      source_row = last_row - 1
      target_row = last_row

      # Adjust row numbers in formulas
      def shift_row(match):
          col = match.group(1)  # Column letters (may have $)
          row = int(match.group(2))
          return f"{col}{row + 1}"

      requests = []
      for col in columns:
          src_cell = f"{col}{source_row}"
          formula = self.worksheet.acell(src_cell, value_render_option='FORMULA').value

          if not (formula and formula.startswith('=')):
              raise ValueError(f"No formula found in {src_cell}.")

          adjusted_formula = re.sub(r'(\$?[A-Z]+)\$?(\d+)', shift_row, formula)

          # Convert column letter to zero-based index
          col_index = gspread.utils.a1_to_rowcol(f"{col}1")[1] - 1

          requests.append({
              "updateCells": {
                  "rows": [{
                      "values": [{
                          "userEnteredValue": {"formulaValue": adjusted_formula}
                      }]
                  }],
                  "range": {
                      "sheetId": self.worksheet.id,
                      "startRowIndex": target_row - 1,  # zero-based
                      "endRowIndex": target_row,
                      "startColumnIndex": col_index,
                      "endColumnIndex": col_index + 1
                  },
                  "fields": "userEnteredValue"
              }
          })

      # Send all updates in a single API call
      self.spreadsheet.batch_update({"requests": requests})

      log.info(f"Formulas copied for columns {columns} from row {source_row} to {target_row}.")


  def check_values_in_columns(self, target_values):
      """
      Check if all three values match in columns A, B, and C of a Google Sheet.

      Args:
          sheet: gspread worksheet object
          target_values: 
              - a list of values to match (from leftmost column)
      Returns:
          bool: True if all three columns match, False otherwise
      """

      found=False
      # Get all values from columns A, B, and C
      try:
          # Get the range A:C (all rows in columns A, B, C)
          range_data = self.worksheet.get('A:C')

          log.debug('Checking each row')    
          for row in range_data:
              converted_row=self.convert_types(row)[:len(target_values)]
              if converted_row==target_values:
                  log.info('Found a matching row')
                  found=True
          
      except Exception as e:
          log.error(f"Error accessing sheet: {e}")
          return True

      return found
