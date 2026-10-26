#!/usr/bin/env python3
"""
Extract bank / UPI SMS from a QKSMS backup and anonymise them into a test corpus
for the money tracker's SMS parser.

The input is the JSON written by Settings -> Backup in QKSMS (see BackupRepositoryImpl):

    {"messageCount": N, "messages": [{"type": 1, "address": "AD-HDFCBK-S", "date": 1760000000000, "body": "..."}]}

Outputs (both in --out, which is gitignored):
    bank_sms_corpus.json   anonymised messages, safe to review and copy into the test resources
    review.txt             original vs anonymised text for every kept message. CONTAINS PERSONAL DATA:
                           read it to check the anonymisation, then delete it

Only the standard library is used, so it runs on the macOS system python3 (3.9+).
"""

import argparse
import collections
import datetime
import json
import os
import random
import re
import sys

# Bank name -> substrings of the sender header (the part between the operator prefix and the -S/-T/-P suffix)
BANKS = [
    ("HDFC", ("HDFC",)),
    ("ICICI", ("ICICI",)),
    ("SBI", ("SBI",)),
    ("AXIS", ("AXIS",)),
    ("KOTAK", ("KOTAK", "KMBL", "KMBANK")),
    ("PAYTM", ("PAYTMB", "PYTMBK", "PAYTMBK")),
    ("AIRTEL", ("AIRBNK",)),
]

# Merchants and brands that are kept as-is so category rules can be tested
MERCHANTS = {
    "AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA", "MEESHO", "SWIGGY", "ZOMATO", "BLINKIT", "ZEPTO",
    "BIGBASKET", "DMART", "INSTAMART", "DUNZO", "UBER", "OLA", "RAPIDO", "IRCTC", "MAKEMYTRIP", "GOIBIBO",
    "REDBUS", "INDIGO", "BOOKMYSHOW", "NETFLIX", "SPOTIFY", "HOTSTAR", "JIOHOTSTAR", "PRIME", "YOUTUBE",
    "GOOGLE", "APPLE", "JIO", "AIRTEL", "VODAFONE", "BSNL", "ACT", "TATA", "TATAPLAY", "BESCOM", "TNEB",
    "MSEDCL", "ADANI", "HPCL", "BPCL", "IOCL", "SHELL", "APOLLO", "PHARMEASY", "NETMEDS", "1MG", "LIC",
    "ZERODHA", "GROWW", "UPSTOX", "CRED", "PHONEPE", "PAYTM", "GPAY", "BHIM", "AMAZONPAY", "RELIANCE",
    "STARBUCKS", "DOMINOS", "MCDONALDS", "KFC", "DECATHLON", "IKEA", "CROMA", "LENSKART", "URBANCLAP",
    "URBAN", "COMPANY", "FASTAG", "NHAI", "RAZORPAY", "PAYU", "BILLDESK", "CCAVENUE", "CASHFREE",
}

# Words that end a name, or mean the text after a keyword wasn't a name at all
STOPWORDS = {
    "A", "AC", "A/C", "ACCT", "ACCOUNT", "AND", "AT", "ATM", "AVL", "AVAILABLE", "BAL", "BALANCE", "BANK",
    "BANKING", "BLOCK", "BY", "CALL", "CARD", "CARDHOLDER", "CREDIT", "CREDITED", "CUSTOMER", "DATE", "DEAR",
    "DEBIT", "DEBITED", "DT", "FOR", "FROM", "HAS", "IF", "IMPS", "IN", "INFO", "INR", "IS", "LINKED", "MOB",
    "MOBILE", "NEFT", "NET", "NOT", "OF", "ON", "OR", "POS", "REF", "REFNO", "RRN", "RS", "RTGS", "SAVINGS",
    "SB", "SIR", "SMS", "THE", "TO", "TXN", "UPI", "USER", "VIA", "VPA", "WITH", "YOU", "YOUR", "TOWARDS",
    "THANK", "THANKS", "TOTAL", "AMT", "AMOUNT", "MIN", "DUE", "OTP", "EMI", "LTD", "LIMITED", "PVT",
    "HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "MAHINDRA", "PAYMENTS", "STATE", "INDIA",
}

FIRST_NAMES = ["ARJUN", "PRIYA", "RAHUL", "ANANYA", "VIKRAM", "SNEHA", "KARAN", "DIVYA", "ROHAN", "MEERA",
               "ADITYA", "KAVYA", "SURESH", "LAKSHMI", "MANOJ", "POOJA", "NIKHIL", "ISHA", "DEEPAK", "RIYA"]
LAST_NAMES = ["SHARMA", "IYER", "REDDY", "NAIR", "GUPTA", "MENON", "PATEL", "RAO", "SINGH", "DAS",
              "KULKARNI", "JOSHI", "PILLAI", "VERMA", "BOSE", "SHETTY", "MEHTA", "GOWDA", "KHAN", "SEN"]
SHOP_NAMES = ["SUNRISE STORES", "GREEN LEAF CAFE", "CITY MEDICALS", "STAR TRADERS", "NEW BHARAT MART",
              "LOTUS ENTERPRISES", "RIVERSIDE FUELS", "GOLDEN BAKERY", "METRO ELECTRONICS", "PARK FOODS"]

MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"

HEADER_RE = re.compile(r"^(?:[A-Z]{2}-)?([A-Z0-9]{3,10})(?:-([PSTG]))?$")

URL_RE = re.compile(r"\b(?:https?://)?((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|in|io|co|me|ly|link|net|org|bank))(/[^\s]*)?",
                    re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
VPA_RE = re.compile(r"\b([\w.-]+)@([A-Za-z][A-Za-z0-9]*)\b")
AMOUNT_RE = re.compile(
    r"(?P<pre>\b(?:Rs|INR|USD|US\$|EUR|GBP|AED|SGD)\.?\s*|₹\s*"
    r"|\b(?:debited|credited)\s+(?:by|for|with)\s+"
    r"|\b(?:Avl\.?\s*Bal(?:ance)?|Available\s+Balance|Bal(?:ance)?)\s*(?:is|:|-)?\s*(?:Rs\.?|INR|₹)?\s*)"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE)
DATE_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}[-/.](?:\d{1,2}|" + MONTHS + r")[-/.]\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s?" + MONTHS + r"\s?\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?\b", re.IGNORECASE),
]
MASKED_ACCOUNT_RE = re.compile(r"(?<![A-Za-z0-9])([Xx*]{1,12})(\d{3,6})\b")
LABELLED_ACCOUNT_RE = re.compile(
    r"\b((?:ending(?:\s+(?:with|in))?|last\s+4\s+digits|card(?:\s+no\.?)?|a/c\s+no\.?|ac\s+no\.?|account\s+no\.?)\s*:?\s*)(\d{4,})",
    re.IGNORECASE)
CUSTOMER_ID_RE = re.compile(r"\b((?:Cust(?:omer)?\.?\s*ID|CRN|Client\s+ID|User\s+ID)\s*[:.]?\s*)((?=[A-Z0-9]*\d)[A-Z0-9]{3,})",
                            re.IGNORECASE)
TOLL_FREE_RE = re.compile(r"(?<!\d)(?:1800|1860)(?:[\s-]?\d){4,7}(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(\+?91[\s-]?)?([6-9]\d{9})(?!\d)")
LONG_NUMBER_RE = re.compile(r"(?<![\d.,])\d{5,}(?![\d,]|\.\d)")
DEAR_RE = re.compile(r"\b(Dear\s+)([A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3})(?=\s*[,:!])")

NAME = r"[A-Z][A-Za-z.&'-]*(?:[ \t]+[A-Z][A-Za-z.&'-]*){0,4}"
NAME_CONTEXT_RES = [
    # "trf to NAME Refno", "To NAME On", "from NAME", "at MERCHANT on"
    re.compile(r"(?P<pre>(?i:\b(?:trf\s+to|transfer(?:red)?\s+to|paid\s+to|sent\s+to|received\s+from|credited\s+by"
               r"|debited\s+by|by|to|from|towards|at|info:?)\s+))(?P<name>" + NAME + ")"),
    # "NAME has requested money", at the start of a sentence
    re.compile(r"(?P<pre>(?:^|(?<=[.!?\n]))\s*)(?P<name>" + NAME + r")(?=\s+has\s+(?:requested|sent|paid|transferred))"),
    # ICICI: "; NAME credited"
    re.compile(r"(?P<pre>;\s*)(?P<name>" + NAME + r")(?=\s+credited)"),
    # Axis: "UPI/P2A/<ref>/NAME"
    re.compile(r"(?P<pre>\b(?:UPI|IMPS|NEFT|RTGS)/[A-Z0-9]+/[^/\s]*/)(?P<name>[A-Za-z][A-Za-z .&'-]*?)"
               r"(?=\s*(?:/|\n|$|\.\s|\s+Not\b|\s+Avl\b))"),
]
MERCHANT_CONTEXTS = {"at", "towards", "info", "info:"}

PLACEHOLDER_RE = re.compile("\ue000(\\d+)\ue001")
OTHER_DIGITS_RE = re.compile(r"\d{4,}")


class Anonymiser:
    """Replaces personal data with consistent fakes: the same original value always gets the same
    replacement within one run, so duplicate alerts (bank + UPI app) still match after anonymising."""

    def __init__(self, rng, fuzz_amounts, redact_words):
        self.rng = rng
        self.fuzz_amounts = fuzz_amounts
        self.redact_words = [w for w in redact_words if w]
        self.maps = collections.defaultdict(dict)
        self.vpa_counter = 0

    def _mapped(self, kind, key, make):
        table = self.maps[kind]
        if key not in table:
            table[key] = make()
        return table[key]

    def _digits(self, kind, digits):
        def make():
            if kind == "phone":
                first = digits[0]
            else:
                first = str(self.rng.randint(1, 9)) if digits[0] != "0" else "0"
            return first + "".join(str(self.rng.randint(0, 9)) for _ in digits[1:])
        return self._mapped(kind, digits, make)

    def _fake_person(self, original):
        words = len(original.split())

        def make():
            name = self.rng.choice(FIRST_NAMES)
            if words > 1:
                name += " " + self.rng.choice(LAST_NAMES)
            return name
        fake = self._mapped("person", original.upper(), make)
        return fake if original.isupper() else fake.title()

    def _fake_shop(self, original):
        fake = self._mapped("shop", original.upper(), lambda: self.rng.choice(SHOP_NAMES))
        return fake if original.isupper() else fake.title()

    def anonymise(self, body):
        """Returns (anonymised body, shape, list of (kind, original, replacement), review flags)."""
        slots = []  # (final text, tag used for the shape)
        changes = []

        def hold(final, tag):
            slots.append((final, tag))
            return "\ue000%d\ue001" % (len(slots) - 1)

        def sub(regex, text, fn):
            return regex.sub(fn, text)

        text = body

        def url(m):
            host, path = m.group(1), m.group(2) or ""
            final = m.group(0).replace(path, "/x" if path else "")
            if path:
                changes.append(("url", m.group(0), final))
            return hold(final, "<URL>")
        text = sub(EMAIL_RE, text, lambda m: (changes.append(("email", m.group(0), "user@example.com")),
                                              hold("user@example.com", "<EMAIL>"))[1])
        text = sub(URL_RE, text, url)

        def vpa(m):
            local, handle = m.group(1), m.group(2)
            if any(merchant in local.upper() for merchant in MERCHANTS):
                return hold(m.group(0), "<VPA>")
            if local.isdigit():
                fake_local = self._digits("phone", local)
            else:
                def make():
                    self.vpa_counter += 1
                    return "payee%d" % self.vpa_counter
                fake_local = self._mapped("vpa", local.lower(), make)
            final = "%s@%s" % (fake_local, handle)
            changes.append(("vpa", m.group(0), final))
            return hold(final, "<VPA>")
        text = sub(VPA_RE, text, vpa)

        def amount(m):
            pre, num = m.group("pre"), m.group("num")
            if self.fuzz_amounts:
                whole, _, fraction = num.partition(".")
                plain = whole.replace(",", "")
                fake = iter(self._digits("amount", plain))
                fake_whole = "".join(next(fake) if c.isdigit() else c for c in whole)
                num = fake_whole + ("." + fraction if fraction else "")
            return hold(pre + num, pre + "<AMT>")
        text = sub(AMOUNT_RE, text, amount)

        for regex in DATE_RES:
            text = sub(regex, text, lambda m: hold(m.group(0), "<DATE>"))

        def masked_account(m):
            final = m.group(1) + self._digits("account", m.group(2))
            changes.append(("account", m.group(0), final))
            return hold(final, m.group(1) + "<ACCT>")
        text = sub(MASKED_ACCOUNT_RE, text, masked_account)

        def labelled_account(m):
            final = m.group(1) + self._digits("account", m.group(2)[-4:]).rjust(len(m.group(2)), "X")
            changes.append(("account", m.group(0), final))
            return hold(final, m.group(1) + "<ACCT>")
        text = sub(LABELLED_ACCOUNT_RE, text, labelled_account)

        for original, fake in list(self.maps["account"].items()):
            regex = re.compile(r"(?<![\d\ue000])%s(?![\d\ue001])" % original)
            if regex.search(text):
                changes.append(("account", original, fake))
                text = regex.sub(lambda m: hold(fake, "<ACCT>"), text)

        def customer_id(m):
            final = m.group(1) + "".join(c if not c.isdigit() else str(self.rng.randint(0, 9)) for c in m.group(2))
            changes.append(("customer id", m.group(0), final))
            return hold(final, m.group(1) + "<ID>")
        text = sub(CUSTOMER_ID_RE, text, customer_id)

        text = sub(TOLL_FREE_RE, text, lambda m: hold(m.group(0), "<TOLLFREE>"))

        def phone(m):
            final = (m.group(1) or "") + self._digits("phone", m.group(2))
            changes.append(("phone", m.group(0), final))
            return hold(final, "<PHONE>")
        text = sub(PHONE_RE, text, phone)

        def long_number(m):
            final = self._digits("number", m.group(0))
            changes.append(("number", m.group(0), final))
            return hold(final, "<NUM>")
        text = sub(LONG_NUMBER_RE, text, long_number)

        def dear(m):
            if m.group(2).split()[0].upper() in STOPWORDS:
                return m.group(0)
            changes.append(("name", m.group(2), "Customer"))
            return m.group(1) + hold("Customer", "Customer")
        text = sub(DEAR_RE, text, dear)

        for regex in NAME_CONTEXT_RES:
            def name(m):
                pre, matched = m.group("pre"), m.group("name")
                kept = []
                for token in re.finditer(r"\S+", matched):
                    if token.group(0).strip(".,;:").upper() in STOPWORDS:
                        break
                    kept.append(token)
                if not kept:
                    return m.group(0)
                original = matched[kept[0].start():kept[-1].end()].rstrip(".,;:'-&")
                if not original:
                    return m.group(0)
                kept = original.split()
                rest = matched[len(original):]
                if any(token.strip(".,&'-").upper() in MERCHANTS for token in kept):
                    return pre + hold(original, "<MERCHANT>") + rest
                if pre.strip().lower() in MERCHANT_CONTEXTS:
                    final = self._fake_shop(original)
                else:
                    final = self._fake_person(original)
                changes.append(("name", original, final))
                return pre + hold(final, "<NAME>") + rest
            text = sub(regex, text, name)

        for word in self.redact_words:
            regex = re.compile(r"\b%s\b" % re.escape(word), re.IGNORECASE)

            def redact(m):
                final = self._fake_person(m.group(0))
                changes.append(("redacted word", m.group(0), final))
                return hold(final, "<NAME>")
            text = sub(regex, text, redact)

        flags = []
        if OTHER_DIGITS_RE.search(PLACEHOLDER_RE.sub("", text)):
            flags.append("unmasked number of 4+ digits")

        final = PLACEHOLDER_RE.sub(lambda m: slots[int(m.group(1))][0], text)
        shape = PLACEHOLDER_RE.sub(lambda m: slots[int(m.group(1))][1], text)
        shape = re.sub(r"\s+", " ", re.sub(r"\d", "9", shape)).strip().lower()
        return final, shape, changes, flags


def bank_for(header, extra_banks):
    for name, needles in extra_banks + BANKS:
        if any(needle in header for needle in needles):
            return name
    return None


def looks_like_money(body):
    return bool(re.search(r"(?:Rs\.?|INR|₹)\s*\d", body, re.IGNORECASE)) and \
        bool(re.search(r"debit|credit|spent|sent|paid|received|withdrawn", body, re.IGNORECASE))


def load_messages(paths):
    seen = set()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            backup = json.load(f)
        for message in backup.get("messages", []):
            key = (message.get("address"), message.get("date"), message.get("body"))
            if key not in seen:
                seen.add(key)
                yield message


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("backups", nargs="+", help="QKSMS backup-*.json file(s)")
    parser.add_argument("--out", default=os.path.join(here, "out"), help="output directory (default: tools/bank-sms/out)")
    parser.add_argument("--per-shape", type=int, default=3,
                        help="keep at most this many messages with the same template (default 3, 0 = all)")
    parser.add_argument("--since", help="only messages on or after this date, YYYY-MM-DD")
    parser.add_argument("--keep-amounts", action="store_true", help="keep real amounts instead of replacing their digits")
    parser.add_argument("--redact", action="append", default=[], metavar="WORD",
                        help="always replace this word, e.g. your own name (repeatable)")
    parser.add_argument("--bank", action="append", default=[], metavar="NAME=HEADER",
                        help="extra bank, e.g. --bank IDFC=IDFCFB (repeatable)")
    parser.add_argument("--include-unknown", action="store_true",
                        help="also keep money-like messages from alphanumeric senders that aren't a known bank")
    parser.add_argument("--seed", type=int, help="random seed, only for reproducible test runs")
    args = parser.parse_args()

    extra_banks = []
    for spec in args.bank:
        name, _, header = spec.partition("=")
        if not header:
            parser.error("--bank must look like NAME=HEADER")
        extra_banks.append((name.upper(), (header.upper(),)))

    since_ms = None
    if args.since:
        since = datetime.datetime.strptime(args.since, "%Y-%m-%d")
        since_ms = int(since.timestamp() * 1000)

    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    anonymiser = Anonymiser(rng, fuzz_amounts=not args.keep_amounts, redact_words=args.redact)

    candidates = []
    unknown_senders = collections.Counter()
    total = 0
    for message in load_messages(args.backups):
        total += 1
        if message.get("type") != 1:  # inbox only
            continue
        if since_ms and message.get("date", 0) < since_ms:
            continue
        address = (message.get("address") or "").strip().upper()
        body = message.get("body") or ""
        match = HEADER_RE.match(address)
        if not match or not re.search("[A-Z]", match.group(1)):
            continue  # a phone number, i.e. a person
        header, kind = match.group(1), match.group(2)
        bank = bank_for(header, extra_banks)
        if bank is None:
            if looks_like_money(body):
                unknown_senders[address] += 1
                if not args.include_unknown:
                    continue
                bank = "UNKNOWN"
            else:
                continue
        candidates.append((bank, address, kind, message.get("date", 0), body))

    # Newest first, so the corpus reflects the formats banks use today
    candidates.sort(key=lambda c: c[3], reverse=True)

    per_shape = collections.Counter()
    kept = []
    for bank, address, kind, date, body in candidates:
        anonymised, shape, changes, flags = anonymiser.anonymise(body)
        per_shape[(bank, shape)] += 1
        if args.per_shape and per_shape[(bank, shape)] > args.per_shape:
            continue
        kept.append(dict(bank=bank, sender=address, senderType=kind, date=date, body=body,
                         anonymised=anonymised, shape=shape, changes=changes, flags=flags))

    kept.sort(key=lambda k: (k["bank"], -k["date"]))
    counters = collections.Counter()
    corpus = []
    for entry in kept:
        counters[entry["bank"]] += 1
        entry["id"] = "%s-%03d" % (entry["bank"], counters[entry["bank"]])
        corpus.append(collections.OrderedDict([
            ("id", entry["id"]),
            ("bank", entry["bank"]),
            ("sender", entry["sender"]),
            ("senderType", entry["senderType"]),
            ("date", datetime.datetime.fromtimestamp(entry["date"] / 1000).strftime("%Y-%m-%d")),
            ("body", entry["anonymised"]),
            ("similarMessages", per_shape[(entry["bank"], entry["shape"])]),
            ("needsReview", entry["flags"]),
            ("expected", None),
        ]))

    os.makedirs(args.out, exist_ok=True)
    corpus_path = os.path.join(args.out, "bank_sms_corpus.json")
    with open(corpus_path, "w", encoding="utf-8") as f:
        json.dump({"source": "QKSMS backup, anonymised by tools/bank-sms/extract_bank_sms.py",
                   "amountsFuzzed": not args.keep_amounts,
                   "count": len(corpus),
                   "messages": corpus}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    review_path = os.path.join(args.out, "review.txt")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write("CONTAINS PERSONAL DATA - check the anonymisation, then delete this file.\n\n")
        for entry in kept:
            f.write("=== %s  %s%s\n" % (entry["id"], entry["sender"],
                                       "  [REVIEW: %s]" % ", ".join(entry["flags"]) if entry["flags"] else ""))
            f.write("ORIGINAL:   %s\n" % entry["body"].replace("\n", "\n            "))
            f.write("ANONYMISED: %s\n" % entry["anonymised"].replace("\n", "\n            "))
            for kind, original, replacement in entry["changes"]:
                f.write("    %-13s %s -> %s\n" % (kind, original, replacement))
            f.write("\n")

    # Only counts and sender headers go to the terminal, never message text
    print("Read %d messages, %d from bank senders, kept %d (at most %s per template)."
          % (total, len(candidates), len(corpus), args.per_shape or "all"))
    for bank, count in sorted(counters.items()):
        print("  %-8s %d" % (bank, count))
    flagged = sum(1 for entry in kept if entry["flags"])
    if flagged:
        print("%d message(s) flagged for review (see needsReview)." % flagged)
    if unknown_senders and not args.include_unknown:
        print("Money-like messages from senders that aren't in the bank list (add with --bank NAME=HEADER):")
        for address, count in unknown_senders.most_common(15):
            print("  %-14s %d" % (address, count))
    print("Corpus: %s" % corpus_path)
    print("Review: %s  <- contains personal data, delete after checking" % review_path)


if __name__ == "__main__":
    sys.exit(main())
