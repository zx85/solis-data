# Google doings
import gspread  # pip install gspread
# Setting up the authorization
from google.oauth2.service_account import Credentials
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
