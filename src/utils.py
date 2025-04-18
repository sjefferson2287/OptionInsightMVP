def trend_direction(prices):
    if prices is None or len(prices) < 2:
        return "neutral"
    return "up" if prices[-1] > prices[0] else "down"
