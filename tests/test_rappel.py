import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rappelConsoHA'))
import rappel_script as script

SAMPLE_CONFIG = {
    "distributeurs": ["lidl"],
    "produits": ["fromage", "saumon"],
    "surveillance": ["guigoz"],
}

SAMPLE_DATA_CACHE = {
    "count": 2,
    "new_count": 0,
    "stale": False,
    "last_update": "2026-06-01T10:00:00",
    "keywords_used": ["fromage", "saumon"],
    "distributeurs_used": ["lidl"],
    "surveillance_used": ["guigoz"],
    "data": [{"titre": "fromage fondu", "marque": "test", "numero_fiche": "2026-01-0001"}],
    "nouveaux": [],
}


class TestRappelResilience(unittest.TestCase):

    def setUp(self):
        import logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        import logging
        logging.disable(logging.NOTSET)

    def test_stale_fallback_on_url_error(self):
        """3 URLError → retour du data cache avec stale=True, new_count=0."""
        with patch.object(script, 'get_config', return_value=SAMPLE_CONFIG):
            with patch('rappel_script.urllib.request.urlopen',
                       side_effect=urllib.error.URLError("timeout")):
                with patch.object(script, 'load_data_cache',
                                  return_value=SAMPLE_DATA_CACHE):
                    with patch('rappel_script.time.sleep') as mock_sleep:
                        result = script.fetch_recalls()

        self.assertTrue(result["stale"])
        self.assertIn("stale_since", result)
        self.assertEqual(result["new_count"], 0)
        self.assertEqual(result["nouveaux"], [])
        self.assertEqual(mock_sleep.call_count, 2)

    def test_no_retry_on_4xx(self):
        """HTTP 400 → pas de retry, retour d'erreur avec stale=False."""
        http_400 = urllib.error.HTTPError(
            url='', code=400, msg='Bad Request', hdrs={}, fp=None)
        with patch.object(script, 'get_config', return_value=SAMPLE_CONFIG):
            with patch('rappel_script.urllib.request.urlopen',
                       side_effect=http_400):
                with patch('rappel_script.time.sleep') as mock_sleep:
                    result = script.fetch_recalls()

        mock_sleep.assert_not_called()
        self.assertFalse(result.get("stale"))
        self.assertIn("error", result)

    def test_data_cache_saved_on_success(self):
        """Succès API → save_data_cache appelé avec stale=False."""
        api_response = {"results": [], "total_count": 0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(api_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(script, 'get_config', return_value=SAMPLE_CONFIG):
            with patch('rappel_script.urllib.request.urlopen',
                       return_value=mock_resp):
                with patch.object(script, 'load_cache', return_value={}):
                    with patch.object(script, 'save_cache'):
                        with patch.object(script, 'save_data_cache') as mock_save:
                            result = script.fetch_recalls()

        mock_save.assert_called_once()
        saved_arg = mock_save.call_args[0][0]
        self.assertFalse(saved_arg["stale"])
        self.assertFalse(result.get("stale"))


if __name__ == '__main__':
    unittest.main()
