"""Independent measurements disclose differences without altering predictions."""

import unittest

from damage_lab.validation import compare


class ValidationTests(unittest.TestCase):
    """Prediction checks report arithmetic rather than calibrating a model."""

    def test_mismatch_reports_the_original_prediction_and_signed_error(self):
        self.assertEqual(compare(117, 156), {
            "predicted": 117, "measured": 156, "difference": -39,
            "relative_error": -0.25, "measured_to_predicted": 1.3333333333333333,
        })

    def test_zero_measurement_has_no_relative_error(self):
        self.assertEqual(compare(117, 0), {
            "predicted": 117, "measured": 0, "difference": 117,
            "relative_error": None, "measured_to_predicted": 0,
        })

    def test_zero_prediction_has_no_measurement_ratio(self):
        self.assertEqual(compare(0, 156), {
            "predicted": 0, "measured": 156, "difference": -156,
            "relative_error": -1, "measured_to_predicted": None,
        })

    def test_boolean_inputs_cannot_be_damage_numbers(self):
        with self.assertRaisesRegex(ValueError, "Predicted DPS must be a finite nonnegative number"):
            compare(True, 156)

    def test_overflowed_ratios_cannot_be_reported(self):
        with self.assertRaisesRegex(ValueError, "Comparison relative_error must be finite"):
            compare(1e308, 1e-308)

    def test_both_zero_values_keep_both_ratios_undefined(self):
        self.assertEqual(compare(0, 0), {
            "predicted": 0, "measured": 0, "difference": 0,
            "relative_error": None, "measured_to_predicted": None,
        })

    def test_equal_values_report_zero_error_without_a_completeness_claim(self):
        self.assertEqual(compare(83.7, 83.7), {
            "predicted": 83.7, "measured": 83.7, "difference": 0,
            "relative_error": 0, "measured_to_predicted": 1,
        })

    def test_negative_prediction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Predicted DPS must be a finite nonnegative number"):
            compare(-17, 156)

    def test_negative_measurement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Measured DPS must be a finite nonnegative number"):
            compare(117, -23)

    def test_boolean_measurement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Measured DPS must be a finite nonnegative number"):
            compare(117, False)

    def test_nonfinite_prediction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Predicted DPS must be a finite nonnegative number"):
            compare(float("nan"), 156)

    def test_nonfinite_measurement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Measured DPS must be a finite nonnegative number"):
            compare(117, float("inf"))

    def test_numeric_text_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Predicted DPS must be a finite nonnegative number"):
            compare("117", 156)

    def test_missing_measurement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Measured DPS must be a finite nonnegative number"):
            compare(117, None)

    def test_inverse_ratio_overflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Comparison measured_to_predicted must be finite"):
            compare(1e-308, 1e308)
