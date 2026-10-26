# Bank SMS test corpus

`extract_bank_sms.py` turns a QKSMS backup into an anonymised set of bank and UPI SMS, to use as
test data for the money tracker's parser. It uses only the Python standard library, so it runs on
the macOS system `python3` with nothing to install.

## 1. Get a backup from your phone

1. In QKSMS on the phone: **Settings → Backup → Backup now**. The file is saved as
   `QKSMS/Backups/backup-<timestamp>.json` in the phone's storage.
2. Copy it to `tools/bank-sms/input/` (USB file transfer, or `adb pull` if you already use adb).

`input/`, `out/` and any `backup-*.json` are gitignored, so the real backup can't be committed by accident.

## 2. Run it

```bash
python3 tools/bank-sms/extract_bank_sms.py tools/bank-sms/input/backup-*.json --redact "YourFirstName"
```

Useful options:

| Option | What it does |
|---|---|
| `--redact WORD` | Always replace this word, e.g. your own or family names (repeatable) |
| `--since 2025-01-01` | Only recent messages, since bank formats change |
| `--per-shape 3` | Keep at most 3 messages per template (default 3, `0` keeps all) |
| `--bank IDFC=IDFCFB` | Add a bank by its sender header (repeatable) |
| `--include-unknown` | Also keep money-like messages from senders not in the bank list |
| `--keep-amounts` | Keep real amounts (by default their digits are replaced) |

The terminal only shows counts and sender headers, never message text. It also lists senders that
look like banks but aren't in the list, so you can add them with `--bank`.

## 3. Review, then copy into the tests

The script writes two files to `tools/bank-sms/out/`:

- `bank_sms_corpus.json`: the anonymised messages. Each has `"expected": null`, to be filled in
  with the correct parse result (or marked as not a transaction).
- `review.txt`: the original and anonymised text side by side, with every replacement listed.
  **It contains your personal data.** Check it, especially entries marked `REVIEW`, then delete it.

Once the corpus looks clean, copy it to the parser's test resources and commit it from there.

## What gets replaced

Replacements are consistent within a run: the same account, reference number, amount or person
always gets the same fake value, so duplicate alerts (for example a bank SMS and a Paytm Bank SMS
for the same payment) still match.

| Data | Example | Becomes |
|---|---|---|
| Account and card digits | `A/C *4821`, `XX907`, `Card 5521`, `ending 9087` | same mask, different digits, including repeats like `SMS BLOCK 907` |
| UPI IDs | `rakesh.verma@okaxis`, `9876501234@ybl` | `payee1@okaxis`, fake number (the handle is kept, since it identifies the app) |
| Reference numbers, OTPs, other long numbers | `629812345671` | random digits, same length |
| Phone numbers | `9215676766` | fake mobile number (bank toll-free 1800/1860 numbers are kept) |
| Names | `To Ramesh Kumar`, `; ANITA DESAI credited`, `UPI/P2A/…/Mohan Lal`, `Priya Nair has requested`, `Dear Nikhil,` | fake names in the same case, `Dear Customer` |
| Unknown shops | `at BLUE MOON RESTAURANT` | a fake shop name |
| Amounts | `Rs.1,250.00` | same format, different digits |
| Links | `https://hdfcbk.io/a/Xy12Ab` | `https://hdfcbk.io/x` |

Known merchants (Swiggy, Zomato, Amazon, IRCTC, …) and bank names are kept so category rules can
be tested. Dates, times and message layout are kept as-is.

The anonymisation is pattern-based, so it can miss things. Always read `review.txt` before
committing a corpus.

`sample_backup.json` is a small backup with made-up messages, for trying the script out.
