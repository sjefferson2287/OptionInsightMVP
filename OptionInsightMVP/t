warning: in the working copy of 'main.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/main.py b/main.py[m
[1mindex 4c07249..f8cfced 100644[m
[1m--- a/main.py[m
[1m+++ b/main.py[m
[36m@@ -10,90 +10,132 @@[m [mfrom src.greeks import compute_greeks[m
 from src.report import generate_report[m
 [m
 def load_config():[m
[31m-    with open("config.json", "r") as f:[m
[31m-        return json.load(f)[m
[32m+[m[32m    """Loads configuration from config.json"""[m
[32m+[m[32m    try:[m
[32m+[m[32m        with open("config.json", "r") as f:[m
[32m+[m[32m            return json.load(f)[m
[32m+[m[32m    except FileNotFoundError:[m
[32m+[m[32m        print("Error: config.json not found. Please create it.")[m
[32m+[m[32m        return None[m
[32m+[m[32m    except json.JSONDecodeError:[m
[32m+[m[32m        print("Error: config.json is not valid JSON.")[m
[32m+[m[32m        return None[m
 [m
 def main(symbols=None, expiration=None):[m
[31m-    # 1) Load settings[m
[31m-    config            = load_config()[m
[31m-    symbols           = symbols or config.get("symbols", [])[m
[31m-    expiration        = expiration if expiration is not None else config.get("expiration")[m
[31m-    lookback          = config.get("lookback_days", 30)[m
[31m-    filters           = config.get("filters", {})[m
[31m-    tech_filters      = config.get("technical_filters", {})    # ← grab your RSI/BB settings[m
[32m+[m[32m    """Main function to fetch data, calculate metrics, and generate report."""[m
[32m+[m[32m    config = load_config()[m
[32m+[m[32m    if config is None:[m
[32m+[m[32m        return  # Exit if config loading failed[m
[32m+[m
[32m+[m[32m    # 1) Determine symbols and expiration[m
[32m+[m[32m    symbols_to_run     = symbols if symbols else config.get("symbols", [])[m
[32m+[m[32m    if not symbols_to_run:[m
[32m+[m[32m        print("Error: No symbols specified in config.json or via command line.")[m
[32m+[m[32m        return[m
[32m+[m
[32m+[m[32m    effective_expiration = expiration if expiration is not None else config.get("expiration")[m
[32m+[m
[32m+[m[32m    # 2) Load parameters[m
[32m+[m[32m    lookback           = config.get("lookback_days", 30)[m
[32m+[m[32m    filters            = config.get("filters", {})[m
[32m+[m[32m    tech_filters       = config.get("technical_filters", {})[m
     max_days_to_expiry = config.get("max_days_to_expiry")[m
 [m
     all_results = [][m
 [m
[31m-    for symbol in symbols:[m
[32m+[m[32m    for symbol in symbols_to_run:[m
         print(f"Analyzing {symbol}...")[m
 [m
[31m-        # 2) Stock data & indicators[m
[32m+[m[32m        # --- Stock data & volatility ---[m
         stock_df = get_stock_data(symbol, lookback)[m
[31m-        if stock_df.empty:[m
[32m+[m[32m        if stock_df is None or stock_df.empty:[m
             print(f"  • No stock data for {symbol}, skipping.")[m
             continue[m
[32m+[m[32m        if len(stock_df) < 2:[m
[32m+[m[32m            print(f"  • Only {len(stock_df)} days of data for {symbol}, need ≥2, skipping.")[m
[32m+[m[32m            continue[m
 [m
         last_close = stock_df["Close"].iloc[-1][m
[31m-        hist_vol   = ([m
[31m-            stock_df["Close"][m
[31m-                .pct_change()[m
[31m-                .rolling(window=20).std()[m
[31m-                .iloc[-1][m
[31m-            * (252 ** 0.5)[m
[31m-        )[m
[32m+[m
[32m+[m[32m        # 20‑day rolling std → hist_vol[m
[32m+[m[32m        rolling_std = stock_df["Close"].pct_change().rolling(window=20).std()[m
[32m+[m[32m        if rolling_std.empty:[m
[32m+[m[32m            print(f"  • Not enough data for volatility calc for {symbol}, skipping.")[m
[32m+[m[32m            continue[m
[32m+[m
[32m+[m[32m        last_std = rolling_std.iloc[-1][m
[32m+[m[32m        if isinstance(last_std, pd.Series):[m
[32m+[m[32m            na_flag = last_std.isna().any()[m
[32m+[m[32m        else:[m
[32m+[m[32m            na_flag = pd.isna(last_std)[m
[32m+[m[32m        if na_flag:[m
[32m+[m[32m            print(f"  • Volatility result NaN for {symbol}, skipping.")[m
[32m+[m[32m            continue[m
[32m+[m
[32m+[m[32m        try:[m
[32m+[m[32m            scalar_std = last_std.item() if isinstance(last_std, pd.Series) else last_std[m
[32m+[m[32m            hist_vol = float(scalar_std) * (252 ** 0.5)[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            print(f"  • Error converting volatility to float for {symbol}: {e}, skipping.")[m
[32m+[m[32m            continue[m
[32m+[m
[32m+[m[32m        # --- Indicators ---[m
         indicators = compute_indicators(stock_df)[m
[32m+[m[32m        if indicators is None or indicators.empty:[m
[32m+[m[32m            print(f"  • Indicators failed for {symbol}, skipping.")[m
[32m+[m[32m            continue[m
 [m
[31m-        # 3) Option chain (with your horizon)[m
[32m+[m[32m        # --- Option chain ---[m
         option_chain = get_option_chain([m
             symbol,[m
[31m-            expiration=expiration,[m
[32m+[m[32m            expiration=effective_expiration,[m
             max_days_to_expiry=max_days_to_expiry[m
         )[m
[31m-        if option_chain.empty:[m
[31m-            print(f"  • No options for {symbol} (exp={expiration}), skipping.")[m
[32m+[m[32m        if option_chain is None or option_chain.empty:[m
[32m+[m[32m            print(f"  • No options for {symbol} (exp={effective_expiration}), skipping.")[m
             continue[m
 [m
[31m-        # 4) Theoretical pricing & Greeks[m
[32m+[m[32m        # --- Theoretical pricing & Greeks ---[m
[32m+[m[32m        sigma_val = hist_vol[m
         option_chain = calculate_theoretical_prices([m
             option_chain,[m
             last_close,[m
[31m-            expiration,[m
[31m-            hist_vol=hist_vol[m
[32m+[m[32m            effective_expiration,    # <—— pass expiration here[m
[32m+[m[32m            hist_vol=sigma_val[m
         )[m
[31m-        option_chain = compute_greeks(option_chain, last_close, sigma=hist_vol)[m
[32m+[m[32m        if option_chain is None or option_chain.empty:[m
[32m+[m[32m            print(f"  • Pricing failed for {symbol}, skipping.")[m
[32m+[m[32m            continue[m
 [m
[31m-        # 5) Build report rows, now passing tech_filters[m
[31m-        report = generate_report([m
[31m-            symbol,[m
[31m-            option_chain,[m
[31m-            indicators,[m
[31m-            filters,[m
[31m-            tech_filters[m
[31m-        )[m
[31m-        if not report.empty:[m
[32m+[m[32m        option_chain = compute_greeks(option_chain, last_close, sigma=sigma_val)[m
[32m+[m[32m        if option_chain is None or option_chain.empty:[m
[32m+[m[32m            print(f"  • Greeks failed for {symbol}, skipping.")[m
[32m+[m[32m            continue[m
[32m+[m
[32m+[m[32m        # --- Build your report ---[m
[32m+[m[32m        report = generate_report(symbol, option_chain, indicators, filters, tech_filters)[m
[32m+[m[32m        if report is not None and not report.empty:[m
             all_results.append(report)[m
 [m
[31m-    # 6) Concatenate & save[m
[31m-    valid_results = [df for df in all_results if not df.empty][m
[31m-    if valid_results:[m
[31m-        final_df = pd.concat(valid_results, ignore_index=True)[m
[31m-        os.makedirs("output", exist_ok=True)[m
[31m-        final_df.to_csv("output/report.csv", index=False)[m
[31m-        print("Report saved to output/report.csv")[m
[32m+[m[32m    # --- Save results ---[m
[32m+[m[32m    if all_results:[m
[32m+[m[32m        try:[m
[32m+[m[32m            final_df = pd.concat(all_results, ignore_index=True)[m
[32m+[m[32m            os.makedirs("output", exist_ok=True)[m
[32m+[m[32m            output_file = os.path.join("output", "report.csv")[m
[32m+[m[32m            final_df.to_csv(output_file, index=False)[m
[32m+[m[32m            print(f"Report saved to {output_file}")[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            print(f"Error saving final report: {e}")[m
     else:[m
[31m-        print("No qualifying trades found.")[m
[32m+[m[32m        print("No qualifying trades found across all symbols.")[m
 [m
 if __name__ == "__main__":[m
     parser = argparse.ArgumentParser(description="OptionInsight MVP Scanner")[m
[31m-    parser.add_argument([m
[31m-        "--symbols", nargs="+",[m
[31m-        help="Override tickers (default from config.json)"[m
[31m-    )[m
[31m-    parser.add_argument([m
[31m-        "--expiration", type=str,[m
[31m-        help="Option expiration date (YYYY-MM-DD). Omit to scan all expirations."[m
[31m-    )[m
[32m+[m[32m    parser.add_argument("--symbols", nargs="+",[m
[32m+[m[32m                        help="Override tickers (default from config.json)")[m
[32m+[m[32m    parser.add_argument("--expiration", type=str, default=None,[m
[32m+[m[32m                        help="Option expiration date (YYYY-MM-DD); omit to scan all.")[m
     args = parser.parse_args()[m
 [m
     main(symbols=args.symbols, expiration=args.expiration)[m
