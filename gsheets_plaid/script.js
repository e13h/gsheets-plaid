const SHEET = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
const TRANSACTION_ID_COL = getColumnIndexByName("transaction_id", SHEET);
const AMOUNT_COL = getColumnIndexByName("amount", SHEET);
const SPLIT_COL = getColumnIndexByName("split", SHEET);

function splitTransaction(sheet, row) {
    // Determine number of existing sub-rows
    let transaction_id = sheet.getRange(row, TRANSACTION_ID_COL).getValue();

    // Remove subscript (if any)
    transaction_id = transaction_id.split('-')[0];

    // Find index of last sub-row
    const sub_rows = sheet.getRange(1, 1, sheet.getLastRow()).createTextFinder(transaction_id).findAll();
    const last_sub_row = Math.max(...sub_rows.map((r) => { return r.getLastRow() }));
    const num_sub_rows = sub_rows.length;

    // Insert new row
    sheet.insertRowAfter(last_sub_row);
    const new_transaction_row = last_sub_row + 1;

    // Copy the previous transaction
    const source_range = sheet.getRange(row, 1, 1, sheet.getMaxColumns());
    const destination_range = sheet.getRange(new_transaction_row, 1, 1, sheet.getMaxColumns());
    source_range.copyTo(destination_range);

    // Modify the transaction ID (append num_sub_rows + 1)
    const new_transaction_id = `${transaction_id}-${num_sub_rows}`;
    sheet.getRange(new_transaction_row, TRANSACTION_ID_COL).setValue(new_transaction_id);

    // Clear the amount
    sheet.getRange(new_transaction_row, AMOUNT_COL).clearContent();
}

function getColumnIndexByName(columnName, sheet = null) {
    if (sheet == null) {
        sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Transactions');
    }
    let header = sheet.getRange(1, 1, 1, sheet.getMaxColumns()).getValues()[0];
    return header.indexOf(columnName) + 1;
}

function onEdit(e) {
    const rg = e.range;
    if (rg.getSheet().getName() === "Sheet1"
        && rg.getNumRows() === 1
        && rg.getNumColumns() === 1
        && rg.getColumn() === 7
        && rg.isChecked()
        && !rg.getSheet().getRange(rg.getRow(), TRANSACTION_ID_COL).isBlank()) {

        splitTransaction(sheetName = rg.getSheet(), row = rg.getRow());
        rg.uncheck();
    }
    SHEET.getRange(2, SPLIT_COL, SHEET.getMaxRows()).uncheck();
}