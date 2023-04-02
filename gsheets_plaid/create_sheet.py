import os

import googleapiclient.discovery


def create_new_spreadsheet(
        gsheets_service: googleapiclient.discovery.Resource,
        apps_script_service: googleapiclient.discovery.Resource,
        title: str = 'Finance Tracker') -> str:
    spreadsheet = {'properties': {'title': title}}
    result = gsheets_service.spreadsheets().create(body=spreadsheet).execute()
    spreadsheet_id = result.get("spreadsheetId")
    create_new_apps_script(apps_script_service, title+' Script', spreadsheet_id)
    return spreadsheet_id


def create_new_apps_script(
        apps_script_service: googleapiclient.discovery.Resource,
        title: str,
        spreadsheet_id: str):
    request = {
        'title': title,
        'parentId': spreadsheet_id,
    }
    response = apps_script_service.projects().create(body=request).execute()

    with open(os.path.join(os.path.dirname(__file__), 'script.js')) as f:
        script_code = f.read()
    with open(os.path.join(os.path.dirname(__file__), 'manifest.json')) as f:
        manifest = f.read() 
    request = {
        'files': [{
            'name': 'code',
            'type': 'SERVER_JS',
            'source': script_code
        }, {
            'name': 'appsscript',
            'type': 'JSON',
            'source': manifest
        }]
    }
    response = apps_script_service.projects().updateContent(
        body=request,
        scriptId=response['scriptId']).execute()
