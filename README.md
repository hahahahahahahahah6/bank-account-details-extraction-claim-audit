# Documentation claim auditor

An offline audit tool that compares documentation about the checked capability with static call patterns in Python source. It reads root README.md and Markdown files with a docs path component, excludes fenced code, and includes inline code. It never executes the inspected source or contacts a service. It makes no network requests, writes no audit files, and sends no telemetry.

Install and run:

```sh
python3 -m pip install .
bank-account-details-extraction-claim-audit audit . --json
python3 -m bank_account_details_extraction_claim_audit audit . --verbose
bank-account-details-extraction-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
python3 -m bank_account_details_extraction_claim_audit --version
python3 -m unittest discover
```

The optional repository defaults to the current directory. Each ignore option takes one relative path prefix, matched by path components. The default failure threshold is high; medium also fails on evidence found only in tests. Exit status is 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. JSON includes a verdict, findings with rule, severity, message and locations, plus production and test evidence. A PASS can still contain a medium finding below the selected threshold.

The two finding identifiers are:

```text
documented-bank-account-details-extraction-claim-false
documented-no-bank-account-details-extraction-claim-false
```

A documented positive without production evidence produces HIGH, or MEDIUM when evidence exists only in tests. A documented denial conflicting with production evidence produces HIGH. A positive without any source produces HIGH; a denial without source passes. With no matched documentation, the audit passes.

Matching lowercases text, expands negative contractions, replaces hyphens with spaces and collapses whitespace within paragraphs. It uses exact phrases with word boundaries, longest first and alphabetical ties. Listed denial spans are removed before positives. The vocabulary is defined in the package's phrases module. Other Markdown outside the selected paths is ignored. Source is parsed with ast; invalid syntax supplies no evidence. Symlinked files and directories are excluded. Files in fixtures, docs or examples never supply production evidence. Files in tests, or whose names begin with test_ or end with _test.py, supply separate test evidence.

Evidence requires a listed generic attribute call on any base, an imported generic callable (including aliases), or a Mindee client construction and matching product parse in one module. Bare generic names without an import do not count. Imports alone do not count. Assignments, annotated assignments, context manager bindings and local function, method or class definitions can shadow imported names. The tracer is conservative and module scoped; it does not combine a client in one file with a parse in another.

This is static pattern matching rather than semantic judgement. Dead code counts; indirect alias chains can be missed. Denial handling depends on the fixed list. Terms for storing, displaying, managing or templating account records can cause false positives when embedded in matched wording. Payment forms collecting payout details have the same ambiguity. The French acronym can also denote meat or anatomy, causing cooking, butchery and medical false positives. A renderer or keyword highlighter may describe itself with matched wording. Photographing a document or OCRing it into raw text can likewise be described using matched scanning language without structured fields. Generic calls can actually parse user-typed strings; such calls still count. Human review must interpret the documentation and code together.

The French name relevé d'identité bancaire and its variants are not checked: apostrophe spelling varies and normalization does not strip apostrophes. Only the listed English names and acronym forms are checked. Claims about IBAN alone, plain text alone, templates, form filling, account verification or ownership checks are outside the phrase vocabulary. Exact substring matching still applies if longer wording includes a listed phrase.

The supported Mindee products and their fields are:

```text
BankAccountDetailsV1: account_holder_name, iban, swift
BankAccountDetailsV2: account_holders_names, bban (bban_bank_code,
  bban_branch_code, bban_number, bban_key), iban, swift_code
```

Neither product provides bank name, branch address, account type or payment status. This tool checks the product call, not the presence or quality of fields. Both products exist in SDK 4.22.0 and remain in SDK 5.4.0 under the v1 product namespace; the fingerprint is not exclusive to the 4.x series. Detection does not establish that a current API request succeeds. Azure Document Intelligence, Mindee and Veryfi are cloud services; static inspection does not establish runtime configuration or successful calls.

Other Mindee products are outside the checked operation:

```text
InvoiceV4, ReceiptV5, PassportV1, FinancialDocumentV1, BankCheckV1,
PayslipV2, PayslipV3, HealthcareCardV1, BusinessCardV1, CustomV1,
GeneratedV1, BillOfLadingV1, ResumeV1, DeliveryNoteV1, DriverLicenseV1,
IdCardV1, InternationalIdV2, CarteGriseV1, EnergyBillV1
```

Checks and statements are different documents from account detail slips, even when they contain account numbers. Configurable Mindee v2 model IDs supply no fixed fingerprint. Azure calls with any model ID are excluded: its models include statements and checks but no product for the checked capability. Veryfi calls of any kind, including hypothetical methods, are excluded: SDK 5.1.0 has no corresponding method and its generic documents HTTP endpoint serves multiple document types. Google Document AI calls with any processor and Eden AI universal calls with any model are excluded because neither documents a dedicated product for the checked operation.

LlamaParse is generative and has no fixed fingerprint. Nanonets, Docsumo, ABBYY Vantage, Rossum, Klippa, Parseur and Extend use opaque model, skill, queue, template or workflow IDs, or generic uploads configured elsewhere; their calls are excluded. Textract's document, expense and identity analysis operations are excluded, including asynchronous analysis and expense retrieval. It has no dedicated operation for the checked capability.

Bank and open-banking API calls read account data rather than fields from a document and are excluded. Schwifty and other IBAN or BIC validation libraries operate on strings already available to the caller and are excluded. Plain PDF text readers, OCR, CSV and spreadsheet readers, and table extraction libraries supply no evidence. Hand-written regular expressions over OCR text plus manual field assembly are missed without a listed call. Subprocess wrappers around Mindee, Veryfi or any other external CLI are excluded by design.

Claims about other document families are outside this vocabulary: invoices, receipts, identity documents, passports, bank checks, bank statements, tax forms including W2 and 1099, pay stubs, health insurance cards, business cards, credit cards, contracts, mortgages, resumes, bills of lading, delivery notes, vehicle registrations, energy bills and marriage certificates. This audit covers only the checked feature and cannot establish end-to-end correctness.

The package uses the MIT license and supports Python 3.9 or later.
