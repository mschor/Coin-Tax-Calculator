# Coin-Tax-Calculator
Simple program to calculate capital gains or losses using a fills file from Coinbase Pro.

Doesn't yet make a distinction between long-term and short-term gains; although that would be simple enough to add.

It outputs:
* A file of all transaction records (token, cost, proceeds, gain/loss)
* A file of all unsold lots
* A separate file for partially sold lots

I needed to figure out my own taxes this year and it was very complicated because I wrote a small trading bot who was busy making a few dollars here and there.

The way this program works is that it uses the FIFO method to calculate capital gains as follows:

1) It categorizes and sorts all of your transactions per token and per "side" (buy or sell) and by date
2) It then iterates over all of your SELL transactions; one token at a time
3) It examines the first BUY transaction for that token.
4) If that lot is not large enough to cover the SELL, it loops over additional BUYs and averages them until it can process the SELL.
5) It spits out your total cost and total proceeds
6) It also prints a list of BUY transactions that had no corresponding SELL. So you probably want to store that info for next year.

Note: Purchase fees are included when calculating the cost and sell fees are subtracted when calculating proceeds. I believe that's the correct handling for tax purposes (someone please tell me if I'm wrong).

# Prerequisite
Python 3

# Usage
Generate a fills file from January 1st to December 31st of the prior year (as all transactions are currently considered to be short-term)

python3 coin_tax_calc.py <fills.csv>

It if fails because it can't find BUY txns that pre-date a SELL, generate a fills file going back further and drop in the needed BUY record(s)

# Disclaimer: While this program is simple, there could be mistakes; so I cannot give any gurantees that this is calculating your own personal taxes correctly. Please use this program at your own risk and ensure that you are submitting your taxes correctly.
