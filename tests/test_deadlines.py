import unittest
from datetime import date

from tracker.deadlines import find

TODAY = date(2026, 9, 28)


class DeadlineTests(unittest.TestCase):
    def f(self, text, explicit=None):
        return find(text, explicit, today=TODAY)

    def test_google_wording(self):
        self.assertEqual(self.f("<p>Please complete your application before <b>October 9, 2026.</b></p>"),
                         ("2026-10-09", False))

    def test_common_phrasings(self):
        self.assertEqual(self.f("Application deadline: Nov 15, 2026.")[0], "2026-11-15")
        self.assertEqual(self.f("Applications will be accepted until 10/31/2026.")[0], "2026-10-31")
        self.assertEqual(self.f("This posting closes on 2026-12-01.")[0], "2026-12-01")
        self.assertEqual(self.f("Apply by January 5th for priority consideration.")[0], "2027-01-05")
        self.assertEqual(self.f("Submit your application no later than 15 October 2026.")[0], "2026-10-15")

    def test_rolling(self):
        self.assertEqual(self.f("Applications accepted on an ongoing basis until the position is filled."), (None, True))
        self.assertEqual(self.f("We review applications on a rolling basis."), (None, True))

    def test_ignores_other_dates(self):
        self.assertEqual(self.f("Must be graduating between December 2027 and June 2028."), (None, False))
        self.assertEqual(self.f("Internship dates: June 1, 2027 to August 20, 2027."), (None, False))
        self.assertEqual(self.f("Founded in 2010, we build things."), (None, False))

    def test_explicit_field(self):
        self.assertEqual(self.f("", "2026-11-01T23:59:00-04:00"), ("2026-11-01", False))


if __name__ == "__main__":
    unittest.main()
