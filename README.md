# Coin-Tax-Calculator
Simple program to calculate capital gains or losses using a Coinbase Pro fills file.

Doesn't yet make a distinction between long-term and short-term gains; although that would be simple enough to add.

Sorry, that's all it does. I needed to figure out my own taxes this year and it was very complicated because I wrote a small trading bot who was busy making a few dollars here and there.

The way it works is that it uses the FIFO method to calculate capital gains as follows:

1) It iterates over all of your SELL transactions; one token at a time
2) It examines the first BUY transaction for that token.
3) If that lot is not large enough to cover the SELL, it loops over additional BUYs and averages them until it can process the SELL.
4) It spits out your total cost and total proceeds

Note: Purchase fees are included when calculating the cost and subtracted when calculating proceeds. I believe that's the correct handling for tax purposes. Someone please tell me if I'm wrong.

# Prerequisite
Python 3

# Usage
python3 coin_tax_calc.py <fills.csv>

# Disclaimer: While this program is simple, there could be mistakes; so I cannot give any gurantees that this is calculating your own personal taxes correctly. Please use this program at your own risk and ensure that you are submitting your taxes correctly.
