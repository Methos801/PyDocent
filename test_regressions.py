import unittest
from unittest.mock import patch

import checker
from lessons import loader


class RegressionTests(unittest.TestCase):
    def test_remote_host_is_rejected(self):
        import app
        with patch.dict('os.environ', {'TUTOR_HOST': '0.0.0.0', 'TUTOR_NO_BROWSER': '1'}):
            with self.assertRaises(ValueError):
                app.main()

    def test_only_progress_routes_are_available(self):
        import app
        client = app.app.test_client()
        base = app.UI_ORIGIN
        headers = {"X-Tutor-Token": app.LAUNCH_TOKEN}
        self.assertEqual(client.get("/api/progress", base_url=base).status_code, 401)
        self.assertEqual(client.post("/api/run", base_url=base, headers=headers).status_code, 404)
        self.assertEqual(client.post("/api/check", base_url=base, headers=headers).status_code, 404)
        self.assertEqual(client.post("/api/save", base_url=base, headers=headers, json=[1]).status_code, 400)
        self.assertEqual(client.post("/api/save", base_url=base, headers=headers, json={"lesson_id": "x"}).status_code, 400)
        foreign = {**headers, "Origin": "http://127.0.0.1:9999"}
        self.assertEqual(client.get("/api/progress", base_url=base, headers=foreign).status_code, 403)

    def test_lesson_solutions_pass(self):
        for lesson in loader.load_all():
            challenge = next(s for s in lesson["sections"] if s["type"] == "challenge")
            with self.subTest(lesson=lesson["id"]):
                self.assertTrue(checker.evaluate(challenge["check"], challenge["solution"])["passed"])

    def test_unrelated_output_does_not_pass_first_challenge(self):
        challenge = next(s for s in loader.load_one(1)["sections"] if s["type"] == "challenge")
        self.assertFalse(checker.evaluate(challenge["check"], "print(42)")["passed"])

    def test_named_greeting(self):
        challenge = next(s for s in loader.load_one(1)["sections"] if s["type"] == "challenge")
        for output, expected in [("Hello, World!", False), ("hello", False),
                                 ("Hello, my name is!", False), ("Hello, my name is 123!", False),
                                 ("Hello, my name is Alex!", True), ("hello my name is Zoë", True),
                                 ("Hello, my name is 李!", True), ("Hello, my name is Anne-Marie!", True)]:
            with self.subTest(output=output):
                self.assertEqual(checker.evaluate(challenge["check"], f"print({output!r})")["passed"], expected)

    def test_incorrect_challenges_are_rejected(self):
        bad = {
            2: "my_name='Alex'\nmy_age=16\nprint('unrelated')",
            3: "print('TutorTestName')",
            4: "age=16\nif age >= 18: print('You are a minor')\nelse: print('You are an adult')",
            5: "print('Blast off!')\nfor n in range(10,0,-1): print(n)",
            6: "def double(n): return n*2\nprint(100)",
            7: "hobbies=['a','b','c']\nfor x in hobbies: print('other')",
            8: "name=input()\nnumber=int(input())\ndef cheer(name,number): return f'{name} {number}'\nprint('TutorTestName 7')",
        }
        for lesson_id, code in bad.items():
            challenge = next(s for s in loader.load_one(lesson_id)['sections'] if s['type'] == 'challenge')
            with self.subTest(lesson=lesson_id):
                self.assertFalse(checker.evaluate(challenge['check'], code)['passed'])

    def test_alternate_valid_solutions(self):
        cases = {
            2: "my_name='Zoë'\nmy_age=12\nprint(my_name, my_age)",
            4: "age=16\nif age < 18: print('You are a minor')\nelse: print('You are an adult')",
            5: "for n in reversed(range(1,11)): print(n)\nprint('Blast off!')",
            7: "hobbies=['art','music','games']\nfor item in hobbies: print(item)",
        }
        for lesson_id, code in cases.items():
            challenge = next(s for s in loader.load_one(lesson_id)['sections'] if s['type'] == 'challenge')
            with self.subTest(lesson=lesson_id):
                self.assertTrue(checker.evaluate(challenge['check'], code)['passed'])


if __name__ == "__main__":
    unittest.main()
