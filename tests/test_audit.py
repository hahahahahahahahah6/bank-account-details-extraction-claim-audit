"""Contract tests use temporary repositories and fixed reference literals."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from bank_account_details_extraction_claim_audit.audit import audit, match_phrases, normalize, source_evidence
from bank_account_details_extraction_claim_audit.phrases import BANKACCOUNTDETAILSEXTRACTION, NOBANKACCOUNTDETAILSEXTRACTION, GENERIC_NAMES
from bank_account_details_extraction_claim_audit.__main__ import main

EXPECTED_POS = ('bank account details extraction', 'extract bank account details', 'extracts bank account details', 'extracting bank account details', 'extract bank account detail', 'extracts bank account detail', 'extracting bank account detail', 'bank account details parsing', 'bank account details parser', 'parse bank account details', 'parses bank account details', 'parse bank account detail', 'parses bank account detail', 'bank account details scanning', 'bank account details scanner', 'scan bank account details', 'scans bank account details', 'scan bank account detail', 'scans bank account detail', 'bank details extraction', 'extract bank details', 'extracts bank details', 'extracting bank details', 'extract bank detail', 'extracts bank detail', 'extracting bank detail', 'bank details parsing', 'bank details parser', 'parse bank details', 'parses bank details', 'parse bank detail', 'parses bank detail', 'bank details scanning', 'bank details scanner', 'scan bank details', 'scans bank details', 'scan bank detail', 'scans bank detail', 'rib extraction', 'extract rib', 'extracts rib', 'extracting rib', 'rib parsing', 'rib parser', 'parse rib', 'parses rib', 'rib scanning', 'rib scanner', 'scan rib', 'scans rib')
EXPECTED_NEG = ('no bank account details extraction', 'does not extract bank account details', 'does not extract bank account detail', 'does not support bank account details extraction', 'without bank account details extraction', 'no bank account details parser', 'does not parse bank account details', 'does not parse bank account detail', 'no bank details extraction', 'does not extract bank details', 'does not extract bank detail', 'does not support bank details extraction', 'without bank details extraction', 'no bank details parser', 'does not parse bank details', 'does not parse bank detail', 'no rib extraction', 'does not extract rib', 'does not support rib extraction', 'without rib extraction', 'no rib parser', 'does not parse rib', 'rib extraction not supported', 'no rib scanner')
EXPECTED_NAMES = ('extract_bank_account_details', 'parse_bank_account_details', 'extract_bank_account_detail', 'parse_bank_account_detail', 'extract_bank_details', 'parse_bank_details', 'extract_bank_detail', 'parse_bank_detail', 'extract_rib', 'parse_rib', 'extract_bank_account_details_data', 'parse_bank_account_details_data', 'bank_account_details_extraction', 'bank_account_details_extractor', 'bank_account_details_parser', 'bank_details_extraction', 'bank_details_extractor', 'bank_details_parser', 'extract_bank_account_details_info', 'parse_bank_account_details_info', 'bank_account_details_scan', 'bank_account_details_scanner', 'scan_bank_account_details', 'scan_rib')

class AuditTests(unittest.TestCase):
    def repo(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def cli(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['audit', str(root), '--json', *args])
        return code, json.loads(out.getvalue())

    def test_phrase_oracle(self):
        self.assertEqual(BANKACCOUNTDETAILSEXTRACTION, EXPECTED_POS)
        self.assertEqual(NOBANKACCOUNTDETAILSEXTRACTION, EXPECTED_NEG)
        self.assertEqual(GENERIC_NAMES, EXPECTED_NAMES)
        self.assertEqual((len(EXPECTED_POS), len(EXPECTED_NEG), len(set(EXPECTED_NAMES))), (50, 24, 24))

    def test_good(self):
        self.assertEqual(self.cli(self.repo({'README.md': 'bank account details extraction', 'app.py': 'x.extract_bank_account_details()'}))[0], 0)

    def test_bad(self):
        code, result = self.cli(self.repo({'README.md': 'bank account details extraction'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-bank-account-details-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertIn('test_evidence', result)
        self.assertIn('production_evidence', result)

    def test_denial(self):
        code, result = self.cli(self.repo({'README.md': 'no bank account details extraction', 'app.py': 'x.extract_bank_account_details()'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-bank-account-details-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')

    def test_no_source_denial(self):
        self.assertEqual(audit(self.repo({'README.md': 'no bank account details extraction'}))['verdict'], 'PASS')

    def test_no_claim(self):
        self.assertEqual(audit(self.repo({'README.md': 'neutral', 'app.py': 'x.extract_bank_account_details()'}))['verdict'], 'PASS')

    def test_test_only(self):
        for filename in ('tests/helper.py', 'test_feature.py', 'feature_test.py'):
            with self.subTest(filename=filename):
                root = self.repo({'README.md': 'bank account details extraction', filename: 'x.extract_bank_account_details()'})
                code, result = self.cli(root)
                self.assertEqual(code, 0)
                self.assertEqual(result['verdict'], 'PASS')
                self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
                code, result = self.cli(root, '--fail-on', 'medium')
                self.assertEqual(code, 2)
                self.assertEqual(result['verdict'], 'FAIL')

    def test_ignore_component_prefix(self):
        root = self.repo({'README.md': 'bank account details extraction', 'src/a.py': 'x.extract_bank_account_details()'})
        self.assertEqual(self.cli(root, '--ignore', 'sr')[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'src')[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', str(root), '--ignore', '../outside']), 1)
            self.assertEqual(main(['audit', str(root), '--ignore', '/abs']), 1)

    def test_fences(self):
        for fence in ('```', '~~~', '   ````'):
            root = self.repo({'README.md': fence + '\nbank account details extraction\n' + fence})
            self.assertEqual(audit(root)['verdict'], 'PASS')
        root = self.repo({'README.md': '`bank account details extraction`'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_boundaries_longest_denial(self):
        yes, no = match_phrases('extract bank account details')
        self.assertEqual([p[0] for p in yes], ['extract bank account details'])
        self.assertFalse(match_phrases('preextract bank account detailsuffix')[0])
        yes, no = match_phrases('does not extract bank account details')
        self.assertEqual(yes, [])
        self.assertEqual([p[0] for p in no], ['does not extract bank account details'])
        self.assertEqual(match_phrases("doesn't extract bank account details")[0], [])
        self.assertEqual(normalize('BANK-ACCOUNT-DETAILS  extraction'), 'bank account details extraction')

    def test_invalid_encoding_declaration(self):
        root = self.repo({'README.md': 'bank account details extraction', 'app.py': '# coding: nonexistent-r205\nx.extract_bank_account_details()'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_attribute_assignment_preserves_import(self):
        self.assertTrue(source_evidence('import mindee\nmindee.setting = True\nmindee.Client()\nx.parse(BankAccountDetailsV1)'))

    def test_single_module(self):
        root = self.repo({'README.md': 'bank account details extraction', 'one.py': 'import mindee\nc=mindee.Client()', 'two.py': 'x.parse(product.BankAccountDetailsV1)'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_paths_and_ignore(self):
        for folder in ('fixtures', 'docs', 'examples'):
            root = self.repo({'README.md': 'bank account details extraction', folder+'/a.py': 'x.extract_bank_account_details()'})
            self.assertEqual(self.cli(root)[0], 2)
        root = self.repo({'nested/docs/a.md': 'bank account details extraction', 'other.md': 'no bank account details extraction', 'vendor/a.py': 'x.extract_bank_account_details()'})
        self.assertEqual(self.cli(root)[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'vendor', '--ignore', 'unused')[0], 2)
        self.assertEqual(self.cli(root, '--ignore', 'nested')[0], 0)

    def test_symlinks(self):
        root = self.repo({'README.md': 'bank account details extraction'})
        outside = self.repo({'a.py': 'x.extract_bank_account_details()', 'a.md': 'bank account details extraction'})
        (root/'link.py').symlink_to(outside/'a.py')
        (root/'linked').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.cli(root)[0], 2)
        (root/'README.md').unlink()
        (root/'README.md').symlink_to(outside/'a.md')
        self.assertEqual(audit(root)['verdict'], 'PASS')

    def test_usage_io(self):
        for argv in ([], ['audit', '--fail-on', 'HIGH'], ['audit', '--unknown']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(argv)
            self.assertEqual(caught.exception.code, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', '/nonexistent/r205']), 1)
        root = self.repo({})
        root.chmod(0)
        try:
            with self.assertRaises(OSError): audit(root)
        finally:
            root.chmod(0o700)

    def test_entry_points(self):
        root = self.repo({})
        command = [sys.executable, '-m', 'bank_account_details_extraction_claim_audit']
        self.assertEqual(subprocess.check_output(command+['--version'], text=True).strip(), '0.1.0')
        result = subprocess.run(command+['audit', str(root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'PASS')

    def test_positive_000(self):
        self.assertTrue(source_evidence('x.extract_bank_account_details()'))

    def test_positive_001(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details as run\nrun()'))

    def test_positive_002(self):
        self.assertTrue(source_evidence('x.parse_bank_account_details()'))

    def test_positive_003(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details as run\nrun()'))

    def test_positive_004(self):
        self.assertTrue(source_evidence('x.extract_bank_account_detail()'))

    def test_positive_005(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_detail as run\nrun()'))

    def test_positive_006(self):
        self.assertTrue(source_evidence('x.parse_bank_account_detail()'))

    def test_positive_007(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_detail as run\nrun()'))

    def test_positive_008(self):
        self.assertTrue(source_evidence('x.extract_bank_details()'))

    def test_positive_009(self):
        self.assertTrue(source_evidence('from provider import extract_bank_details as run\nrun()'))

    def test_positive_010(self):
        self.assertTrue(source_evidence('x.parse_bank_details()'))

    def test_positive_011(self):
        self.assertTrue(source_evidence('from provider import parse_bank_details as run\nrun()'))

    def test_positive_012(self):
        self.assertTrue(source_evidence('x.extract_bank_detail()'))

    def test_positive_013(self):
        self.assertTrue(source_evidence('from provider import extract_bank_detail as run\nrun()'))

    def test_positive_014(self):
        self.assertTrue(source_evidence('x.parse_bank_detail()'))

    def test_positive_015(self):
        self.assertTrue(source_evidence('from provider import parse_bank_detail as run\nrun()'))

    def test_positive_016(self):
        self.assertTrue(source_evidence('x.extract_rib()'))

    def test_positive_017(self):
        self.assertTrue(source_evidence('from provider import extract_rib as run\nrun()'))

    def test_positive_018(self):
        self.assertTrue(source_evidence('x.parse_rib()'))

    def test_positive_019(self):
        self.assertTrue(source_evidence('from provider import parse_rib as run\nrun()'))

    def test_positive_020(self):
        self.assertTrue(source_evidence('x.extract_bank_account_details_data()'))

    def test_positive_021(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details_data as run\nrun()'))

    def test_positive_022(self):
        self.assertTrue(source_evidence('x.parse_bank_account_details_data()'))

    def test_positive_023(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details_data as run\nrun()'))

    def test_positive_024(self):
        self.assertTrue(source_evidence('x.bank_account_details_extraction()'))

    def test_positive_025(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_extraction as run\nrun()'))

    def test_positive_026(self):
        self.assertTrue(source_evidence('x.bank_account_details_extractor()'))

    def test_positive_027(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_extractor as run\nrun()'))

    def test_positive_028(self):
        self.assertTrue(source_evidence('x.bank_account_details_parser()'))

    def test_positive_029(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_parser as run\nrun()'))

    def test_positive_030(self):
        self.assertTrue(source_evidence('x.bank_details_extraction()'))

    def test_positive_031(self):
        self.assertTrue(source_evidence('from provider import bank_details_extraction as run\nrun()'))

    def test_positive_032(self):
        self.assertTrue(source_evidence('x.bank_details_extractor()'))

    def test_positive_033(self):
        self.assertTrue(source_evidence('from provider import bank_details_extractor as run\nrun()'))

    def test_positive_034(self):
        self.assertTrue(source_evidence('x.bank_details_parser()'))

    def test_positive_035(self):
        self.assertTrue(source_evidence('from provider import bank_details_parser as run\nrun()'))

    def test_positive_036(self):
        self.assertTrue(source_evidence('x.extract_bank_account_details_info()'))

    def test_positive_037(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details_info as run\nrun()'))

    def test_positive_038(self):
        self.assertTrue(source_evidence('x.parse_bank_account_details_info()'))

    def test_positive_039(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details_info as run\nrun()'))

    def test_positive_040(self):
        self.assertTrue(source_evidence('x.bank_account_details_scan()'))

    def test_positive_041(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_scan as run\nrun()'))

    def test_positive_042(self):
        self.assertTrue(source_evidence('x.bank_account_details_scanner()'))

    def test_positive_043(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_scanner as run\nrun()'))

    def test_positive_044(self):
        self.assertTrue(source_evidence('x.scan_bank_account_details()'))

    def test_positive_045(self):
        self.assertTrue(source_evidence('from provider import scan_bank_account_details as run\nrun()'))

    def test_positive_046(self):
        self.assertTrue(source_evidence('x.scan_rib()'))

    def test_positive_047(self):
        self.assertTrue(source_evidence('from provider import scan_rib as run\nrun()'))

    def test_positive_048(self):
        self.assertTrue(source_evidence('import mindee\nfrom mindee.product.fr import BankAccountDetailsV1\nc = mindee.Client()\nc.parse(product.BankAccountDetailsV1)'))

    def test_positive_049(self):
        self.assertTrue(source_evidence('import mindee\nfrom mindee.product.fr import BankAccountDetailsV1\nc = mindee.Client()\nc.parse(BankAccountDetailsV1)'))

    def test_positive_050(self):
        self.assertTrue(source_evidence('import mindee\nfrom mindee.product.fr import BankAccountDetailsV1\nc = mindee.Client()\nc.parse(mindee.product.fr.BankAccountDetailsV1)'))

    def test_positive_051(self):
        self.assertTrue(source_evidence('import mindee\nfrom mindee.product.fr import BankAccountDetailsV1\nc = mindee.Client()\nc.parse(mindee.v1.product.fr.BankAccountDetailsV1)'))

    def test_positive_052(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nc=C()\nx.parse(kind=product.BankAccountDetailsV1)'))

    def test_positive_053(self):
        self.assertTrue(source_evidence('import mindee as m\nfrom mindee import Client as C\nC()\nx.parse(BankAccountDetailsV1)'))

    def test_negative_000(self):
        self.assertEqual(source_evidence('import mindee'), [])

    def test_negative_001(self):
        self.assertEqual(source_evidence('import veryfi'), [])

    def test_negative_002(self):
        self.assertEqual(source_evidence('import azure.ai.documentintelligence'), [])

    def test_negative_003(self):
        self.assertEqual(source_evidence('import google.cloud.documentai'), [])

    def test_negative_004(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()'), [])

    def test_negative_005(self):
        self.assertEqual(source_evidence('extract_bank_account_details()'), [])

    def test_negative_006(self):
        self.assertEqual(source_evidence('x.extract_bank_account_details'), [])

    def test_negative_007(self):
        self.assertEqual(source_evidence('"x.extract_bank_account_details()"'), [])

    def test_negative_008(self):
        self.assertEqual(source_evidence('# x.extract_bank_account_details()'), [])

    def test_negative_009(self):
        self.assertEqual(source_evidence('this is invalid syntax !'), [])

    def test_negative_010(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.InvoiceV4)'), [])

    def test_negative_011(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.ReceiptV5)'), [])

    def test_negative_012(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PassportV1)'), [])

    def test_negative_013(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.FinancialDocumentV1)'), [])

    def test_negative_014(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BankCheckV1)'), [])

    def test_negative_015(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.EnergyBillV1)'), [])

    def test_negative_016(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PayslipV2)'), [])

    def test_negative_017(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PayslipV3)'), [])

    def test_negative_018(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.HealthcareCardV1)'), [])

    def test_negative_019(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BusinessCardV1)'), [])

    def test_negative_020(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.CustomV1)'), [])

    def test_negative_021(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.GeneratedV1)'), [])

    def test_negative_022(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BillOf\x4cadingV1)'), [])

    def test_negative_023(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.\x52esumeV1)'), [])

    def test_negative_024(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.DeliveryNoteV1)'), [])

    def test_negative_025(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.DriverLicenseV1)'), [])

    def test_negative_026(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.IdCardV1)'), [])

    def test_negative_027(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.InternationalIdV2)'), [])

    def test_negative_028(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.\x43arte\x47riseV1)'), [])

    def test_negative_029(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-invoice')"), [])

    def test_negative_030(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-receipt')"), [])

    def test_negative_031(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-layout')"), [])

    def test_negative_032(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-read')"), [])

    def test_negative_033(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-idDocument')"), [])

    def test_negative_034(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-check.us')"), [])

    def test_negative_035(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-tax.us')"), [])

    def test_negative_036(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-bankStatement.us')"), [])

    def test_negative_037(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-payStub.us')"), [])

    def test_negative_038(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-healthInsuranceCard.us')"), [])

    def test_negative_039(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-businessCard')"), [])

    def test_negative_040(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-creditCard')"), [])

    def test_negative_041(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-contract')"), [])

    def test_negative_042(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-mortgage.us.1003')"), [])

    def test_negative_043(self):
        self.assertEqual(source_evidence('veryfi.Client()'), [])

    def test_negative_044(self):
        self.assertEqual(source_evidence('azure.DocumentIntelligenceClient()'), [])

    def test_negative_045(self):
        self.assertEqual(source_evidence('x.process_any_document()'), [])

    def test_negative_046(self):
        self.assertEqual(source_evidence('x.process_any_document_url()'), [])

    def test_negative_047(self):
        self.assertEqual(source_evidence('x.process_document()'), [])

    def test_negative_048(self):
        self.assertEqual(source_evidence('x.process_document_url()'), [])

    def test_negative_049(self):
        self.assertEqual(source_evidence('x.process_w2_document()'), [])

    def test_negative_050(self):
        self.assertEqual(source_evidence('x.process_w9_document()'), [])

    def test_negative_051(self):
        self.assertEqual(source_evidence('x.process_w8_document()'), [])

    def test_negative_052(self):
        self.assertEqual(source_evidence('x.process_check()'), [])

    def test_negative_053(self):
        self.assertEqual(source_evidence('x.process_check_url()'), [])

    def test_negative_054(self):
        self.assertEqual(source_evidence('x.process_check_with_remittance()'), [])

    def test_negative_055(self):
        self.assertEqual(source_evidence('x.process_bank_statement_document()'), [])

    def test_negative_056(self):
        self.assertEqual(source_evidence('x.process_bussines_card_document()'), [])

    def test_negative_057(self):
        self.assertEqual(source_evidence('x.classify_document()'), [])

    def test_negative_058(self):
        self.assertEqual(source_evidence('x.get_business_cards()'), [])

    def test_negative_059(self):
        self.assertEqual(source_evidence('x.process_energy_bill_document()'), [])

    def test_negative_060(self):
        self.assertEqual(source_evidence('x.batch_process_documents()'), [])

    def test_negative_061(self):
        self.assertEqual(source_evidence('x.analyze_document()'), [])

    def test_negative_062(self):
        self.assertEqual(source_evidence('x.analyze_expense()'), [])

    def test_negative_063(self):
        self.assertEqual(source_evidence('x.analyze_id()'), [])

    def test_negative_064(self):
        self.assertEqual(source_evidence('x.start_document_analysis()'), [])

    def test_negative_065(self):
        self.assertEqual(source_evidence('x.get_expense_analysis()'), [])

    def test_negative_066(self):
        self.assertEqual(source_evidence('x.extract_text()'), [])

    def test_negative_067(self):
        self.assertEqual(source_evidence('x.image_to_string()'), [])

    def test_negative_068(self):
        self.assertEqual(source_evidence('x.read_csv()'), [])

    def test_negative_069(self):
        self.assertEqual(source_evidence('x.read_excel()'), [])

    def test_negative_070(self):
        self.assertEqual(source_evidence('x.read_pdf()'), [])

    def test_negative_071(self):
        self.assertEqual(source_evidence('x.convert_into()'), [])

    def test_negative_072(self):
        self.assertEqual(source_evidence('x.extract_table()'), [])

    def test_negative_073(self):
        self.assertEqual(source_evidence('x.extract_tables()'), [])

    def test_negative_074(self):
        self.assertEqual(source_evidence('x.find_tables()'), [])

    def test_negative_075(self):
        self.assertEqual(source_evidence('x.find_table()'), [])

    def test_negative_076(self):
        self.assertEqual(source_evidence('x.get_meter_reading()'), [])

    def test_negative_077(self):
        self.assertEqual(source_evidence('requests.post("https://api.veryfi.com/api/v8/partner/documents")'), [])

    def test_negative_078(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/invoice_parser/affinda"})'), [])

    def test_negative_079(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/\x72esume_parser/affinda"})'), [])

    def test_negative_080(self):
        self.assertEqual(source_evidence('LlamaParse().parse("file")'), [])

    def test_negative_081(self):
        self.assertEqual(source_evidence('nanonets.ocr(model_id="opaque")'), [])

    def test_negative_082(self):
        self.assertEqual(source_evidence('docsumo.upload("file")'), [])

    def test_negative_083(self):
        self.assertEqual(source_evidence('mindee.ClientV2().enqueue_and_parse(model_id="opaque")'), [])

    def test_negative_084(self):
        self.assertEqual(source_evidence('re.search("total", text)'), [])

    def test_negative_085(self):
        self.assertEqual(source_evidence('str.parse("bank account details")'), [])

    def test_negative_086(self):
        self.assertEqual(source_evidence('subprocess.run(["mindee", "parse"])'), [])

    def test_negative_087(self):
        self.assertEqual(source_evidence('subprocess.run(["veryfi", "process"])'), [])

    def test_negative_088(self):
        self.assertEqual(source_evidence('def extract_bank_account_details(): pass\nx.extract_bank_account_details()'), [])

    def test_negative_089(self):
        self.assertEqual(source_evidence('from p import extract_bank_account_details as e\ne = other\ne()'), [])

    def test_negative_090(self):
        self.assertEqual(source_evidence('from p import extract_bank_account_details as e\ne: object = other\ne()'), [])

    def test_negative_091(self):
        self.assertEqual(source_evidence('from p import extract_bank_account_details as e\nwith context() as e:\n e()'), [])

    def test_negative_092(self):
        self.assertEqual(source_evidence('from p import extract_bank_account_details as e\nasync def f():\n async with context() as e:\n  e()'), [])

    def test_negative_093(self):
        self.assertEqual(source_evidence('import mindee\nclass Client: pass\nmindee.Client()\nx.parse(BankAccountDetailsV1)'), [])

    def test_negative_094(self):
        self.assertEqual(source_evidence('from p import extract_bank_account_details\nclass X:\n def extract_bank_account_details(self): pass\nx.extract_bank_account_details()'), [])


    def test_readme_self_audit(self):
        readme = Path(__file__).resolve().parents[1] / 'README.md'
        self.assertEqual(self.cli(self.repo({'README.md': readme.read_text()}))[0], 0)

    def test_console_entry_point(self):
        # Exercise the actual console entry callable even in an uninstalled checkout.
        import importlib.metadata
        try:
            dist = importlib.metadata.distribution('bank-account-details-extraction-claim-audit')
        except importlib.metadata.PackageNotFoundError:
            from importlib.metadata import EntryPoint
            entry = EntryPoint(name='bank-account-details-extraction-claim-audit',
                value='bank_account_details_extraction_claim_audit.__main__:main', group='console_scripts')
        else:
            entry = next(e for e in dist.entry_points if e.name == 'bank-account-details-extraction-claim-audit')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            entry.load()(['--version'])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), '0.1.0')

    def test_cli_usage_errors(self):
        for args in ([], ['audit', '--fail-on', 'HIGH'], ['audit', '--ignore', 'a', 'b', 'c'], ['unknown']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code, 1)

    def test_all_phrase_matches(self):
        for phrase in EXPECTED_POS:
            with self.subTest(phrase=phrase):
                self.assertEqual([p[0] for p in match_phrases(phrase)[0]], [phrase])
        for phrase in EXPECTED_NEG:
            with self.subTest(phrase=phrase):
                yes, no = match_phrases(phrase)
                self.assertEqual(yes, [])
                self.assertEqual([p[0] for p in no], [phrase])

    def test_dead_code_counts_without_execution(self):
        root = self.repo({'README.md': EXPECTED_POS[0], 'app.py': 'raise RuntimeError()\nif False: x.extract_rib()'})
        self.assertEqual(self.cli(root)[0], 0)

    def test_alphabetical_tie(self):
        from bank_account_details_extraction_claim_audit.audit import _matches
        self.assertEqual([p[0] for p in _matches('bb aa', ('bb', 'aa'))], ['aa', 'bb'])

    def test_extra_positive_000(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details\nextract_bank_account_details()'))

    def test_extra_positive_001(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details\nparse_bank_account_details()'))

    def test_extra_positive_002(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_detail\nextract_bank_account_detail()'))

    def test_extra_positive_003(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_detail\nparse_bank_account_detail()'))

    def test_extra_positive_004(self):
        self.assertTrue(source_evidence('from provider import extract_bank_details\nextract_bank_details()'))

    def test_extra_positive_005(self):
        self.assertTrue(source_evidence('from provider import parse_bank_details\nparse_bank_details()'))

    def test_extra_positive_006(self):
        self.assertTrue(source_evidence('from provider import extract_bank_detail\nextract_bank_detail()'))

    def test_extra_positive_007(self):
        self.assertTrue(source_evidence('from provider import parse_bank_detail\nparse_bank_detail()'))

    def test_extra_positive_008(self):
        self.assertTrue(source_evidence('from provider import extract_rib\nextract_rib()'))

    def test_extra_positive_009(self):
        self.assertTrue(source_evidence('from provider import parse_rib\nparse_rib()'))

    def test_extra_positive_010(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details_data\nextract_bank_account_details_data()'))

    def test_extra_positive_011(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details_data\nparse_bank_account_details_data()'))

    def test_extra_positive_012(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_extraction\nbank_account_details_extraction()'))

    def test_extra_positive_013(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_extractor\nbank_account_details_extractor()'))

    def test_extra_positive_014(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_parser\nbank_account_details_parser()'))

    def test_extra_positive_015(self):
        self.assertTrue(source_evidence('from provider import bank_details_extraction\nbank_details_extraction()'))

    def test_extra_positive_016(self):
        self.assertTrue(source_evidence('from provider import bank_details_extractor\nbank_details_extractor()'))

    def test_extra_positive_017(self):
        self.assertTrue(source_evidence('from provider import bank_details_parser\nbank_details_parser()'))

    def test_extra_positive_018(self):
        self.assertTrue(source_evidence('from provider import extract_bank_account_details_info\nextract_bank_account_details_info()'))

    def test_extra_positive_019(self):
        self.assertTrue(source_evidence('from provider import parse_bank_account_details_info\nparse_bank_account_details_info()'))

    def test_extra_positive_020(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_scan\nbank_account_details_scan()'))

    def test_extra_positive_021(self):
        self.assertTrue(source_evidence('from provider import bank_account_details_scanner\nbank_account_details_scanner()'))

    def test_extra_positive_022(self):
        self.assertTrue(source_evidence('from provider import scan_bank_account_details\nscan_bank_account_details()'))

    def test_extra_positive_023(self):
        self.assertTrue(source_evidence('from provider import scan_rib\nscan_rib()'))

    def test_extra_positive_024(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(BankAccountDetailsV1)'))

    def test_extra_positive_025(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(product_class=BankAccountDetailsV1)'))

    def test_extra_positive_026(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(product.BankAccountDetailsV1)'))

    def test_extra_positive_027(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(product_class=product.BankAccountDetailsV1)'))

    def test_extra_positive_028(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(mindee.product.fr.BankAccountDetailsV1)'))

    def test_extra_positive_029(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(product_class=mindee.product.fr.BankAccountDetailsV1)'))

    def test_extra_positive_030(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(mindee.v1.product.fr.BankAccountDetailsV1)'))

    def test_extra_positive_031(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV1\nC()\nx.parse(product_class=mindee.v1.product.fr.BankAccountDetailsV1)'))

    def test_extra_positive_032(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(BankAccountDetailsV2)'))

    def test_extra_positive_033(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(product_class=BankAccountDetailsV2)'))

    def test_extra_positive_034(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(product.BankAccountDetailsV2)'))

    def test_extra_positive_035(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(product_class=product.BankAccountDetailsV2)'))

    def test_extra_positive_036(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(mindee.product.fr.BankAccountDetailsV2)'))

    def test_extra_positive_037(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(product_class=mindee.product.fr.BankAccountDetailsV2)'))

    def test_extra_positive_038(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(mindee.v1.product.fr.BankAccountDetailsV2)'))

    def test_extra_positive_039(self):
        self.assertTrue(source_evidence('from mindee import Client as C\nfrom mindee.product.fr import BankAccountDetailsV2\nC()\nx.parse(product_class=mindee.v1.product.fr.BankAccountDetailsV2)'))

    def test_extra_positive_040(self):
        self.assertTrue(source_evidence('import mindee as m\nm.Client()\nx.parse(BankAccountDetailsV2)'))

    def test_extra_negative_000(self):
        self.assertEqual(source_evidence('import boto3'), [])

    def test_extra_negative_001(self):
        self.assertEqual(source_evidence('import schwifty'), [])

    def test_extra_negative_002(self):
        self.assertEqual(source_evidence('import azure.ai.formrecognizer'), [])

    def test_extra_negative_003(self):
        self.assertEqual(source_evidence('import pdfplumber'), [])

    def test_extra_negative_004(self):
        self.assertEqual(source_evidence('import fitz'), [])

    def test_extra_negative_005(self):
        self.assertEqual(source_evidence('import pypdf'), [])

    def test_extra_negative_006(self):
        self.assertEqual(source_evidence('import PyPDF2'), [])

    def test_extra_negative_007(self):
        self.assertEqual(source_evidence('import pdfminer'), [])

    def test_extra_negative_008(self):
        self.assertEqual(source_evidence('import pytesseract'), [])

    def test_extra_negative_009(self):
        self.assertEqual(source_evidence('import pandas'), [])

    def test_extra_negative_010(self):
        self.assertEqual(source_evidence('import camelot'), [])

    def test_extra_negative_011(self):
        self.assertEqual(source_evidence('import tabula'), [])

    def test_extra_negative_012(self):
        self.assertEqual(source_evidence('veryfi.process_check_with_remittance_url()'), [])

    def test_extra_negative_013(self):
        self.assertEqual(source_evidence('veryfi.process_bank_statement_document_url()'), [])

    def test_extra_negative_014(self):
        self.assertEqual(source_evidence('veryfi.process_bussines_card_document_url()'), [])

    def test_extra_negative_015(self):
        self.assertEqual(source_evidence('veryfi.get_business_card()'), [])

    def test_extra_negative_016(self):
        self.assertEqual(source_evidence('veryfi.delete_business_card()'), [])

    def test_extra_negative_017(self):
        self.assertEqual(source_evidence('veryfi.process_bank_account_details_document()'), [])

    def test_extra_negative_018(self):
        self.assertEqual(source_evidence('veryfi.process_bank_account_details_document_url()'), [])

    def test_extra_negative_019(self):
        self.assertEqual(source_evidence('abbyy.process("opaque")'), [])

    def test_extra_negative_020(self):
        self.assertEqual(source_evidence('rossum.upload("opaque")'), [])

    def test_extra_negative_021(self):
        self.assertEqual(source_evidence('klippa.parse("opaque")'), [])

    def test_extra_negative_022(self):
        self.assertEqual(source_evidence('parseur.upload("opaque")'), [])

    def test_extra_negative_023(self):
        self.assertEqual(source_evidence('extend.run("opaque")'), [])

    def test_extra_negative_024(self):
        self.assertEqual(source_evidence('bank.get_accounts("opaque")'), [])

    def test_extra_negative_025(self):
        self.assertEqual(source_evidence('open_banking.accounts("opaque")'), [])

    def test_extra_negative_026(self):
        self.assertEqual(source_evidence('schwifty.IBAN("opaque")'), [])

    def test_extra_negative_027(self):
        self.assertEqual(source_evidence('schwifty.BIC("opaque")'), [])

    def test_extra_negative_028(self):
        self.assertEqual(source_evidence('re.findall("iban", text)'), [])

    def test_extra_negative_029(self):
        self.assertEqual(source_evidence('str.parse("already extracted text")'), [])

    def test_extra_negative_030(self):
        self.assertEqual(source_evidence('x.parse(BankAccountDetailsV1)'), [])

    def test_extra_negative_031(self):
        self.assertEqual(source_evidence('mindee.Client()\nx.parse(BankAccountDetailsV2)'), [])

    def test_extra_negative_032(self):
        self.assertEqual(source_evidence('import mindee\nx.parse(BankAccountDetailsV2)'), [])

    def test_extra_negative_033(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client()\nx.parse(TypeBankAccountDetailsV1)'), [])

    def test_extra_negative_034(self):
        self.assertEqual(source_evidence('import mindee\ndef parse(): pass\nx.parse(BankAccountDetailsV2)\nmindee.Client()'), [])

    def test_extra_negative_035(self):
        self.assertEqual(source_evidence('import mindee\nclass BankAccountDetailsV2: pass\nmindee.Client()\nx.parse(BankAccountDetailsV2)'), [])

    def test_extra_negative_036(self):
        self.assertEqual(source_evidence('from mindee import Client as C\nwith context() as C:\n C()\nx.parse(BankAccountDetailsV2)'), [])

    def test_extra_negative_037(self):
        self.assertEqual(source_evidence('from mindee import Client as C\nasync def f():\n async with context() as C:\n  C()\nx.parse(BankAccountDetailsV2)'), [])


if __name__ == '__main__':
    unittest.main()
