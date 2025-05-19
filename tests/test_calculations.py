import unittest
import pandas as pd
import numpy as np
import sys

# Attempt to import the functions to be tested
try:
    from src.financial_utils import calculate_historical_volatility
    from src.pricing_models import black_scholes
except ImportError:
    # Fallback for environments where src might not be directly in PYTHONPATH
    # This assumes tests are run from the root directory of the project
    sys.path.insert(0, '.')
    from src.financial_utils import calculate_historical_volatility
    from src.pricing_models import black_scholes

class TestFinancialCalculations(unittest.TestCase):

    # --- Tests for calculate_historical_volatility ---

    def test_hv_sample_data_calculates_volatility(self):
        """Test with sample data that should produce a known volatility value (or a reasonable range)."""
        # Prices from an online example, log returns are approx:
        # 0.009950, 0.009804, -0.019802, 0.009852
        # std of these log returns is approx 0.01206
        # annualized: 0.01206 * sqrt(252) = 0.1914
        # Using a 4-day window for this small dataset to match manual calculation
        data = {'Close': [100.00, 101.00, 102.00, 100.00, 101.00]} # 5 data points for 4 returns
        df = pd.DataFrame(data)
        # We need window + 1 data points for log returns, then window for std calculation.
        # So for a window of 4, we need 5 data points.
        volatility = calculate_historical_volatility(df, window=4)
        self.assertIsNotNone(volatility)
        self.assertIsInstance(volatility, float)
        # Calculation:
        # Log returns:
        # log(101/100) = 0.00995033
        # log(102/101) = 0.00985220
        # log(100/102) = -0.01980263
        # log(101/100) = 0.00995033
        # std([0.00995033, 0.00985220, -0.01980263, 0.00995033]) = 0.0120601
        # annualized = 0.0120601 * sqrt(252) = 0.19145 (approx)
        self.assertAlmostEqual(volatility, 0.19145, places=4)


    def test_hv_insufficient_data_returns_none(self):
        """Test with insufficient data (less than the window + 1)."""
        data = {'Close': [100, 101, 102]} # 3 data points
        df = pd.DataFrame(data)
        # window is 20, needs 21 data points.
        volatility = calculate_historical_volatility(df, window=20)
        self.assertIsNone(volatility)

    def test_hv_all_same_prices_returns_zero(self):
        """Test with data that has all same prices (log returns are 0, std dev is 0)."""
        data = {'Close': [100.0] * 30} # 30 identical prices
        df = pd.DataFrame(data)
        volatility = calculate_historical_volatility(df, window=20)
        self.assertIsNotNone(volatility)
        self.assertEqual(volatility, 0.0)

    def test_hv_empty_dataframe_returns_none(self):
        """Test with an empty DataFrame."""
        df = pd.DataFrame({'Close': pd.Series(dtype=float)})
        volatility = calculate_historical_volatility(df, window=20)
        self.assertIsNone(volatility)

    def test_hv_none_input_returns_none(self):
        """Test with None as input."""
        volatility = calculate_historical_volatility(None, window=20)
        self.assertIsNone(volatility)

    # --- Tests for Black-Scholes Pricing Model ---

    def test_bs_call_standard_case(self):
        """Test Black-Scholes call option pricing with standard inputs."""
        # S=100, K=100, T=1, r=0.05, sigma=0.2. Expected Call Price ~10.4506
        price = black_scholes(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
        self.assertIsNotNone(price)
        self.assertIsInstance(price, float)
        self.assertAlmostEqual(price, 10.45058, places=4)

    def test_bs_put_standard_case(self):
        """Test Black-Scholes put option pricing with standard inputs."""
        # S=100, K=100, T=1, r=0.05, sigma=0.2. Expected Put Price ~5.5735
        price = black_scholes(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='put')
        self.assertIsNotNone(price)
        self.assertIsInstance(price, float)
        self.assertAlmostEqual(price, 5.57353, places=4)

    def test_bs_call_deep_in_the_money(self):
        """Test call option deep in the money."""
        # S=150, K=100, T=1, r=0.05, sigma=0.2. Expected value approx S - K*exp(-rT) = 150 - 100*exp(-0.05) ~ 54.87
        price = black_scholes(S=150, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
        self.assertIsNotNone(price)
        self.assertGreater(price, 150 - 100 * np.exp(-0.05 * 1) - 1) # Check it's close to intrinsic value accounting for time
        self.assertAlmostEqual(price, 52.4701, places=4) # Using an online calculator for reference

    def test_bs_put_deep_in_the_money(self):
        """Test put option deep in the money."""
        # S=50, K=100, T=1, r=0.05, sigma=0.2. Expected value approx K*exp(-rT) - S = 100*exp(-0.05) - 50 ~ 45.12
        price = black_scholes(S=50, K=100, T=1, r=0.05, sigma=0.2, option_type='put')
        self.assertIsNotNone(price)
        self.assertGreater(price, 100 * np.exp(-0.05 * 1) - 50 - 1)
        self.assertAlmostEqual(price, 47.5290, places=4) # Using an online calculator for reference

    def test_bs_call_at_expiry_T_is_zero(self):
        """Test call option at expiry (T=0). Price should be max(0, S-K)."""
        S, K, r, sigma = 110, 100, 0.05, 0.2
        T = 1e-9 # Very small T to simulate expiry
        expected_price = max(0, S - K)
        calculated_price = black_scholes(S, K, T, r, sigma, option_type='call')
        self.assertAlmostEqual(calculated_price, expected_price, places=3)

    def test_bs_put_at_expiry_T_is_zero(self):
        """Test put option at expiry (T=0). Price should be max(0, K-S)."""
        S, K, r, sigma = 90, 100, 0.05, 0.2
        T = 1e-9 # Very small T
        expected_price = max(0, K - S)
        calculated_price = black_scholes(S, K, T, r, sigma, option_type='put')
        self.assertAlmostEqual(calculated_price, expected_price, places=3)

    def test_bs_zero_volatility_call(self):
        """Test call option with zero volatility."""
        # Price should be max(0, S - K*exp(-rT))
        S, K, T, r = 100, 90, 1, 0.05
        sigma = 1e-9 # Very small sigma
        expected_price = max(0, S - K * np.exp(-r * T))
        calculated_price = black_scholes(S, K, T, r, sigma, option_type='call')
        self.assertAlmostEqual(calculated_price, expected_price, places=3)

    def test_bs_zero_volatility_put(self):
        """Test put option with zero volatility."""
        # Price should be max(0, K*exp(-rT) - S)
        S, K, T, r = 90, 100, 1, 0.05
        sigma = 1e-9 # Very small sigma
        expected_price = max(0, K * np.exp(-r * T) - S)
        calculated_price = black_scholes(S, K, T, r, sigma, option_type='put')
        self.assertAlmostEqual(calculated_price, expected_price, places=3)


if __name__ == '__main__':
    # This allows running the tests from the command line
    # e.g. python tests/test_calculations.py
    unittest.main()
