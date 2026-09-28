import unittest

from tracker.filters import evaluate, grad_window_flag, is_us
from tracker.sources import Job


def job(title, locations=("Seattle, WA",), **kw):
    return Job("test", kw.pop("company", "Acme"), "1", title, "https://x", list(locations), **kw)


class FilterTests(unittest.TestCase):
    def keep(self, *a, **kw):
        return evaluate(job(*a, **kw))[0]

    def test_target_roles_kept(self):
        for t in ["Data Scientist, Product Intern, MS, Summer 2027",
                  "Software Development Engineer Intern - Summer 2027 (USA)",
                  "2027 Intern - Machine Learning Engineer",
                  "Student Researcher, BS/MS, Winter-Summer 2027",
                  "AI Engineer Intern"]:
            self.assertTrue(self.keep(t), t)

    def test_irrelevant_dropped(self):
        for t in ["Internal Communications Manager",          # 'intern' substring
                  "Hardware Engineering Intern, BS/MS, Summer 2027",
                  "Marketing Intern - Summer 2027",
                  "Software Engineer Intern - Fall 2026",
                  "Software Engineer Intern, Summer 2026",
                  "Senior Software Engineer",
                  "Software Engineering Intern - CTJ - TS"]:
            self.assertFalse(self.keep(t), t)

    def test_degree_rules(self):
        self.assertFalse(self.keep("Data Scientist, Research Intern, PhD, Summer 2027"))
        self.assertTrue(self.keep("Research Scientist Intern, PhD or MS, Summer 2027"))
        self.assertFalse(self.keep("Software Engineering Intern, BS, Summer 2027"))
        self.assertTrue(self.keep("Software Engineering Intern, BS/MS, Summer 2027"))

    def test_location(self):
        self.assertTrue(is_us(["Mountain View, CA, USA"]))
        self.assertTrue(is_us(["NYC"]))
        self.assertTrue(is_us(["Canada", "Santa Clara, CA"]))
        self.assertFalse(is_us(["London, UK"]))
        self.assertFalse(is_us(["Toronto, ON"]))
        self.assertTrue(is_us([]))

    def test_sponsorship(self):
        self.assertFalse(self.keep("Software Engineer Intern", sponsorship="U.S. Citizenship is Required"))
        keep, flags = evaluate(job("Software Engineer Intern", sponsorship="Does Not Offer Sponsorship"))
        self.assertTrue(keep)
        self.assertIn("sponsorship", flags[0])

    def test_grad_window(self):
        self.assertIsNotNone(grad_window_flag("Must be graduating between December 2026 and June 2027."))
        self.assertIsNone(grad_window_flag("Graduating between December 2027 and June 2028."))
        self.assertIsNone(grad_window_flag("Currently pursuing a Master's degree."))


if __name__ == "__main__":
    unittest.main()
