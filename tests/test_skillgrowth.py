import math
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from damage_lab.skillgrowth import GrowthError, multiplier


class SkillGrowthTest(unittest.TestCase):
    """Verify an explicit growth operator without selecting a current game profile."""

    def test_profile_thresholds_match_an_independent_level_by_level_oracle(self):
        for first, later in ((.10, .08), (.12, .10), (.37, 0), (0, .19)):
            for level in (1, 20, 21, 29, 30, 31, 38):
                expected = Fraction(1)
                for current in range(21, level + 1):
                    expected *= 1 + Fraction(str(first if current <= 30 else later))
                with self.subTest(first=first, later=later, level=level):
                    self.assertTrue(math.isclose(multiplier(level, first_rate=first, later_rate=later),
                                                 float(expected), rel_tol=1e-12))

    def test_small_rates_survive_large_level_counts(self):
        for level, rate in ((10 ** 12 + 30, 1e-12), (10 ** 20 + 30, 1e-20), (10 ** 320 + 30, 1e-320)):
            with localcontext() as context:
                context.prec = 420
                expected = float(((1 + Decimal.from_float(rate)).ln() * Decimal(level - 30)).exp())
            with self.subTest(level=level, rate=rate):
                self.assertTrue(math.isclose(multiplier(level, first_rate=0, later_rate=rate),
                                             expected, rel_tol=1e-12))

    def test_zero_rates_keep_exact_one_for_arbitrarily_large_levels(self):
        self.assertEqual(multiplier(10 ** 400, first_rate=0, later_rate=0), 1.0)

    def test_large_finite_growth_matches_a_high_precision_oracle(self):
        with localcontext() as context:
            context.prec = 100
            expected = float((Decimal('1.10') ** 10) * (Decimal('1.08') ** 8970))
        self.assertTrue(math.isclose(multiplier(9000, first_rate=.10, later_rate=.08), expected, rel_tol=1e-12))

    def test_level_requires_a_positive_integer(self):
        for level in (True, 0, -3, 21.0, '21', None, Fraction(21)):
            with self.subTest(level=level), self.assertRaises(GrowthError):
                multiplier(level, first_rate=.10, later_rate=.08)

    def test_rates_require_finite_nonnegative_representable_numbers(self):
        for rate in (True, -.1, float('nan'), float('inf'), None, '.10', Fraction(1, 10), 10 ** 400):
            for name in ('first_rate', 'later_rate'):
                with self.subTest(rate=rate, name=name), self.assertRaisesRegex(GrowthError, 'Rates must be'):
                    multiplier(20, **{'first_rate': .10, 'later_rate': .08, name: rate})

    def test_overflow_has_a_controlled_error(self):
        for level, first, later in ((10 ** 400, .1, .08), (40, 1e30, 1e30), (22, 1e308, 0)):
            with self.subTest(level=level), self.assertRaisesRegex(GrowthError, 'Growth exceeds'):
                multiplier(level, first_rate=first, later_rate=later)

    def test_unused_rates_are_validated_before_the_base_level_shortcut(self):
        with self.assertRaises(GrowthError):
            multiplier(1, first_rate=.1, later_rate=float('nan'))

    def test_both_rates_are_required_keyword_arguments(self):
        with self.assertRaises(TypeError):
            multiplier(25, first_rate=.1)


if __name__ == '__main__':
    unittest.main()
