import json
import os
import sys
import unittest
from unittest.mock import patch, mock_open
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'eauQualiteHA'))
import eau_qualite_script as script

SAMPLE_CACHE = {
    "compliant": True,
    "stale": False,
    "sampling_date": "2025-12-29T11:46:00Z",
    "sample_code": "05900338890",
    "commune_name": "LAMBERSART",
    "conclusion": "Eau conforme",
    "network": "Réseau test",
    "bact_compliance": "C",
    "pc_compliance": "C",
    "hardness": "25.0 °F",
    "nitrates": "12.0 mg/L",
    "ph": "7.4",
    "parameters": [],
    "last_update": "2026-06-01T10:00:00",
}


class TestRetryAndStaleFallback(unittest.TestCase):

    def setUp(self):
        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        import logging
        logging.disable(logging.NOTSET)

    def test_stale_fallback_on_url_error(self):
        """3 URLError consécutives → données cache avec stale=True."""
        with patch('eau_qualite_script.urllib.request.urlopen',
                   side_effect=urllib.error.URLError("timeout")):
            with patch('eau_qualite_script.os.path.exists', return_value=True):
                with patch('builtins.open',
                           mock_open(read_data=json.dumps(SAMPLE_CACHE))):
                    with patch('eau_qualite_script.time.sleep') as mock_sleep:
                        result = script.fetch_water_quality("59328")

        self.assertTrue(result["stale"])
        self.assertIn("stale_since", result)
        self.assertEqual(result["commune_name"], "LAMBERSART")
        self.assertEqual(mock_sleep.call_count, 2)

    def test_no_retry_on_4xx(self):
        """HTTP 400 → pas de sleep, retour d'erreur sans stale."""
        http_400 = urllib.error.HTTPError(
            url='', code=400, msg='Bad Request', hdrs={}, fp=None)
        with patch('eau_qualite_script.urllib.request.urlopen',
                   side_effect=http_400):
            with patch('eau_qualite_script.os.path.exists', return_value=False):
                with patch('eau_qualite_script.time.sleep') as mock_sleep:
                    result = script.fetch_water_quality("INVALID")

        mock_sleep.assert_not_called()
        self.assertFalse(result.get("stale"))

    def test_no_cache_on_total_failure(self):
        """3 erreurs 503 sans cache → retour d'erreur avec stale=False."""
        http_503 = urllib.error.HTTPError(
            url='', code=503, msg='Service Unavailable', hdrs={}, fp=None)
        with patch('eau_qualite_script.urllib.request.urlopen',
                   side_effect=http_503):
            with patch('eau_qualite_script.os.path.exists', return_value=False):
                with patch('eau_qualite_script.time.sleep'):
                    result = script.fetch_water_quality("59328")

        self.assertFalse(result.get("stale"))
        self.assertIn("error", result)


if __name__ == '__main__':
    unittest.main()
