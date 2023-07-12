const SHEET = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
const TRANSACTION_ID_COL = getColumnIndexByName("transaction_id", SHEET);
const AMOUNT_COL = getColumnIndexByName("amount", SHEET);
const SPLIT_COL = getColumnIndexByName("split", SHEET);

function splitTransaction(sheet, row) {
    // Determine number of existing sub-rows
    let transaction_id = sheet.getRange(row, TRANSACTION_ID_COL).getValue();

    // Remove subscript (if any)
    transaction_id = transaction_id.split('-')[0];

    // Find index of last row in the transaction group
    const row_group = sheet.getRange(1, 1, sheet.getLastRow()).createTextFinder(transaction_id).findAll();
    const insert_loc = Math.max(...row_group.map((r) => { return r.getLastRow() }));
    const num_child_rows = row_group.length - 1;

    // Insert new row
    if (num_child_rows === 0) {
        sheet.insertRowsAfter(insert_loc, 2);
        fillChildTransactionData(sheet, row, insert_loc + 1, transaction_id, num_child_rows + 1);
        fillChildTransactionData(sheet, row, insert_loc + 2, transaction_id, num_child_rows + 2);
    } else {
        sheet.insertRowAfter(insert_loc);
        fillChildTransactionData(sheet, row, insert_loc + 1, transaction_id, num_child_rows + 1);
    }
}

function fillChildTransactionData(sheet, source_row, dest_row, transaction_id, suffix) {
    // Copy the previous transaction
    const source_range = sheet.getRange(source_row, 1, 1, sheet.getMaxColumns());
    const dest_range = sheet.getRange(dest_row, 1, 1, sheet.getMaxColumns());
    source_range.copyTo(dest_range);
    
    // Modify the transaction ID (append num_child_rows + 1)
    const new_transaction_id = `${transaction_id}-${suffix}`;
    sheet.getRange(dest_row, TRANSACTION_ID_COL).setValue(new_transaction_id);
    
    // Clear the amount
    sheet.getRange(dest_row, AMOUNT_COL).clearContent();
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
        && rg.getColumn() === SPLIT_COL
        && rg.isChecked()
        && !rg.getSheet().getRange(rg.getRow(), TRANSACTION_ID_COL).isBlank()) {

        rg.uncheck();
        splitTransaction(sheetName = rg.getSheet(), row = rg.getRow());
    }
    SHEET.getRange(2, SPLIT_COL, SHEET.getMaxRows()).uncheck();
}