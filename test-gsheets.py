import gspread 
# Setting up the authorization
from google.oauth2.service_account import Credentials
# Define the scope

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

    def get_last_row(self):
        """Returns the last non-empty row as a list."""
        values = self.worksheet.get_all_values()
        if values:
            return values[-1]
        return []

    def append_row(self, row_data):
        """Appends a row to the worksheet."""
        self.worksheet.append_row(row_data)

    def replace_top_row(self, new_row):
            """
            Replaces the first row of the worksheet with the values in new_row.
            """
            # Update the first row with new_row values
            cell_range = f"A1:{gspread.utils.rowcol_to_a1(1, len(new_row))}"
            self.worksheet.update(cell_range, [new_row])

sheet = Spreadsheet(
    creds_file="google.json",
    spreadsheet_name="Solar Database",
    worksheet_name="solar5_latest"
)

print(f'last row is {sheet.get_last_row()}')
