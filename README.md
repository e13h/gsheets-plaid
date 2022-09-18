# GSheets-Plaid
A spring break project to get my bank transaction data in Google Sheets without using Google Apps Script.

`gsheets-plaid` is a tool for getting your raw bank transaction data into a Google Sheets spreadsheet, to enable you to make your own formulas and charts for tracking spending, making goals, etc. This app is 100% free (assuming you don't already have a bunch of Google Cloud projects), but there is a bit of one-time setting up to do to get your Google and Plaid credentials in place.

The [`TUTORIAL`](TUTORIAL.md) contains all the instructions to get you from a fresh install of the package to bank transactions in a Google Sheets file.

Please open an issue if something isn't working or if the documentation isn't clear.

---

## Publishing new releases
(for maintainers)

1. Tag the main branch
```
git tag v[insert-version-here]
```
2. Push latest commits with tags
```
git push origin --tags
```
3. Build repo
```
python -m build
```
4. Upload distribution archives to PyPi
```
python -m twine upload dist/*
```
5. Create new release on GitHub
