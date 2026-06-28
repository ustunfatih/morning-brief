import unittest

import morning_brief_engine as engine


class SanitizerSecurityTests(unittest.TestCase):
    def test_escapes_allowed_attribute_values(self):
        raw = '<img src="https://cdn.example.com/icon.png" alt="bad &quot; quote">'

        sanitized = engine._sanitize_html(raw)

        self.assertIn('alt="bad &quot; quote"', sanitized)

    def test_drops_disallowed_event_attributes(self):
        raw = '<a href="https://example.com/" onclick="alert(1)" class="source-link">link</a>'

        sanitized = engine._sanitize_html(raw)

        self.assertIn('href="https://example.com/"', sanitized)
        self.assertNotIn("onclick", sanitized)

    def test_blocks_unsafe_href_and_img_src_schemes(self):
        raw = (
            '<a href="javascript:alert(1)">bad</a>'
            '<a href="mailto:hello@example.com">mail</a>'
            '<img src="data:text/html;base64,abc" alt="bad">'
            '<img src="https://cdn.example.com/icon.png" alt="ok">'
        )

        sanitized = engine._sanitize_html(raw)

        self.assertNotIn("javascript:", sanitized)
        self.assertNotIn("data:text/html", sanitized)
        self.assertIn('href="mailto:hello@example.com"', sanitized)
        self.assertIn('src="https://cdn.example.com/icon.png"', sanitized)

    def test_removes_dangerous_inline_css(self):
        raw = '<p style="color:#111; background-image:url(javascript:alert(1)); width:100%;">hello</p>'

        sanitized = engine._sanitize_html(raw)

        self.assertIn('style="color:#111;width:100%;"', sanitized)
        self.assertNotIn("background-image", sanitized)
        self.assertNotIn("javascript:", sanitized)


class LogMaskingTests(unittest.TestCase):
    def test_masks_email_addresses_and_tokens(self):
        self.assertEqual(engine._mask_for_log("fatih@example.com"), "f***@example.com")
        self.assertEqual(engine._mask_for_log("abcdefghij"), "ab***ij")
        self.assertEqual(engine._mask_for_log("abc"), "***")


class PortfolioSheetParsingTests(unittest.TestCase):
    def test_extracts_current_dashboard_holdings_only(self):
        rows = [
            [],
            ["Total Portfolio Value"],
            [],
            [],
            [],
            ["Ticker", "Company Name", "Shares", "Current Price"],
            ["SCHD", "Schwab US Dividend Equity ETF", "140,3365196", "$32,09"],
            ["QQQI", "NEOS Nasdaq-100 High Income ETF", "61,37305582", "$54,69"],
            ["BATS:ARKX", "ARK Space & Defense Innovation ETF", "30", "$31,93"],
            ["GLDW", "Closed old row", "0", "$41,84"],
            ["TOTAL", "", "231,71", ""],
            ["", "", "", ""],
        ]

        tickers, display_map = engine._extract_portfolio_tickers_from_rows(
            rows, header_row_num=6, ticker_col="Ticker", holdings_col="Shares"
        )

        self.assertEqual(tickers, ["SCHD", "QQQI", "ARKX"])
        self.assertEqual(display_map["ARKX"], "BATS:ARKX")
        self.assertNotIn("GLDW", tickers)

    def test_parses_turkish_and_us_number_formats(self):
        self.assertEqual(engine._parse_decimal_number("140,3365196"), 140.3365196)
        self.assertEqual(engine._parse_decimal_number("$1.234,56"), 1234.56)
        self.assertEqual(engine._parse_decimal_number("$1,234.56"), 1234.56)


if __name__ == "__main__":
    unittest.main()
