import json
import tempfile
import unittest
from pathlib import Path

from preprocess import read_json_records


class JsonFilterTests(unittest.TestCase):
    def test_filters_json_records_and_keeps_word_type(self):
        data = {
            "channel": {
                "item": [
                    {"word_info": {
                        "word": "사과",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                    {"word_info": {
                        "word": "사과-01",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                    {"word_info": {
                        "word": "ㄱ사과",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                    {"word_info": {
                        "word": "사과ㄱ",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                    {"word_info": {
                        "word": "가",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                    {"word_info": {
                        "word": "빠르다",
                        "word_unit": "단어",
                        "word_type": "고유어",
                        "pos_info": [{"pos": "형용사"}],
                    }},
                    {"word_info": {
                        "word": "컴퓨터",
                        "word_unit": "단어",
                        "word_type": "외래어",
                        "pos_info": [{"pos": "명사"}],
                    }},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            records = list(read_json_records(source))

        self.assertEqual(records, [
            {"word": "사과", "word_type": "고유어"},
            {"word": "컴퓨터", "word_type": "외래어"},
        ])


if __name__ == "__main__":
    unittest.main()