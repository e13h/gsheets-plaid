import googleapiclient.discovery


def create_new_spreadsheet(
        gsheets_service: googleapiclient.discovery.Resource,
        title: str = 'Finance Tracker') -> str:
    spreadsheet = {'properties': {'title': title}}
    result = gsheets_service.spreadsheets().create(body=spreadsheet).execute()
    spreadsheet_id = result.get("spreadsheetId")
    return spreadsheet_id
