#!/usr/bin/env python

import csv
import os
import sys
import argparse
from decimal import *
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser()
    parser._action_groups.pop()
    # parser.add_argument('-b', '--begin_date', help="Begin date (inclusive)", type=lambda s: datetime.strptime(s, '%Y-%m-%d'))
    # parser.add_argument('-e', '--end_date', help="End date (inclusive)", type=lambda s: datetime.strptime(s, '%Y-%m-%d'))
    parser.add_argument('-t', '--token', help="Only process transactions for this crypto token")
    parser.add_argument('-o', '--output_file', default='out.csv', help="Output file containing details of each SELL transaction")
    parser.add_argument('-u', '--unsold_lots_file', default='unsold.csv', help="Output file containing completely unsold lots")
    parser.add_argument('-p', '--partially_sold_lots_file', default='partial_sells.csv', help="Output file containing a paritally unsold lots")
    requiredNamed = parser.add_argument_group('required arguments')
    requiredNamed.add_argument('-f', '--filename', help='Coinbase Pro fills.csv file', required=True)
    return parser.parse_args()

def calculate_cost_avg(total, size):
    if total < 0: # negative dollar value is how cbpro shows 'buy' txns
        total = total * -1
    price_per_share = total / size
    return price_per_share

def main():
    getcontext().prec = 13

    args = parse_args()

    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
    EXPECTED_HEADER = "portfolio,trade id,product,side,created at,size,size unit,price,fee,total,price/fee/total unit"
    OUTPUT_HEADER = ["token", "purch_date", "sell_date", "size", "cost_with_fee", "net_proceeds", "gain"]

    single_token = None
    if args.token:
        single_token = args.token

    fills_file = open(args.filename)
    csvreader = csv.reader(fills_file)

    trades = {}
    rows = []
    i = 0
    for row in csvreader:
        if i == 0:
            if ",".join(row) != EXPECTED_HEADER:
                print("Expected header to be: " + EXPECTED_HEADER)
                print("Because your header is not an exact match, this doc might not be the expected format")
                print("Cannot continue")
                sys.exit(1)
        else:
            token = row[2].split("-")[0]
            if token not in trades:
                trades[token] = { "BUY" : [], "SELL" : [] }
            side = row[3]
            trades[token][side].append(dict(zip(EXPECTED_HEADER.split(","), row)))
            trade = dict(zip(EXPECTED_HEADER.split(","), row))
            trade['created at'] = datetime.strptime(trade['created at'], DATE_FORMAT)
            rows.append(trade)

        i += 1

    # At this point, we have all trades loaded into a dict of tokens as keys with the value being another dict
    # which has two keys: BUY and SELL. The values of each of those are list of trades
    # Go through now and sort them by time so we can use the FIFO method for calculating the cost bases
    for token in trades:
        trades[token]["BUY"] = sorted(trades[token]["BUY"], key = lambda ele: ele['created at'])

    total_gains = 0
    total_proceeds = 0
    total_cost = 0
    extra_buys = []
    all_sell_orders = []

    for token in trades:
        if single_token is not None and token != single_token:
            continue
        current_cost_average = None
        token_dict = trades[token]
        # Do some validation to see if we can calculate gains for this token
        if len(token_dict["BUY"]) == 0 and len(token_dict["SELL"]) > 0:
            print("No BUY transactions found for " + token + ", but " + str(len(token_dict["SELL"])) + " SELL transaction(s) were found")
            print("You may need to reach further back in your history to find that fill")
            print("Once you have that fill, you can just insert the row into slot 1 of the fills file that was just processed")
            sys.exit(1)
        if len(token_dict["SELL"]) > 0 and len(token_dict["BUY"]) > 0:
            if token_dict["SELL"][0]['created at'] < token_dict["BUY"][0]['created at']:
                print("Unable to calculate capital gains for " + token)
                print("There is no purchase record that pre-dates the first sell record.")
                print("You may need to reach further back in your history to find that fill")
                print("Once you have that fill, you can just insert the row into slot 1 of the fills file that was just processed")
                sys.exit(1)

        print("------------------------------------")
        print("Processing trades for token: " + token + "...")
        
        buy_index = 0

        current_cost_average = None
        # Advance through transactions, 1 sell at a time. If there's not remaining tokens in the current_cost_average
        # then calculate a new average and advance the the buy index
        for sell_txn in token_dict["SELL"]:

            sell_size = Decimal(sell_txn['size'])
            print("Processing sell for: " + token + ". Sell size: " + str(sell_size))
            
            if current_cost_average == None:
                current_buy = token_dict["BUY"][buy_index]
                total = Decimal(current_buy['total'])
                size = Decimal(current_buy['size'])
                current_cost_average = { "token" : token, "cost_per_share" : calculate_cost_avg(total, size), "size" : size , 'purch_date' : current_buy['created at']}
                print("Calculating cost avg from BUY txn of size: " + str(size))
                buy_index += 1
                transaction_date = current_buy['created at']
                
            # first check the size of the sell against the current size in the cost avg object
            # while the sell is bigger, need to loop through additional buy txns and calculate the weighted avg until we have enough purchases
            # processed to cover the sell
            while sell_size > current_cost_average['size']:
                transaction_date = "Various"
                if (buy_index > len(token_dict["BUY"]) - 1):
                    print("ERROR: ran out of BUY txns to cover the SELLs for this token")
                    sys.exit(1)
                    break
                next_buy = token_dict["BUY"][buy_index]
                next_buy_total = Decimal(next_buy['total'])
                next_buy_size = Decimal(next_buy['size'])
                next_cost_average = { "cost_per_share" : calculate_cost_avg(next_buy_total, next_buy_size), "size" : next_buy_size , 'purch_date' : next_buy['created at']}
                total_size_of_buys = next_buy_size + current_cost_average['size']
                fractional_size_of_existing_avg = current_cost_average['size'] / total_size_of_buys
                fractional_size_of_new_avg = next_buy_size / total_size_of_buys
                new_cost_avg = (current_cost_average['cost_per_share'] * fractional_size_of_existing_avg) + (next_cost_average['cost_per_share'] * fractional_size_of_new_avg)
                print("Recalculating cost avg by averaging in additional BUY of size: " + str(next_buy_size))
                print("Now holding: " + str(current_cost_average['size']) + " + " + str(next_buy_size) + " = " + str(total_size_of_buys))
                current_cost_average = { "token" : token, "cost_per_share" : new_cost_avg, "size" : total_size_of_buys, "purch_date" : next_cost_average['purch_date']}
                buy_index += 1

            if current_cost_average['purch_date'] > sell_txn['created at']:
                print("Data problem. Not enough shares of " + token + " to cover SELL and next BUY has a date > this sell date")
                print("Details of SELL that could not be covered:")
                print(sell_txn)
                sys.exit(1)
            orig_cost = Decimal(sell_txn['size']) * current_cost_average['cost_per_share']
            cap_gain = Decimal(sell_txn['total']) - orig_cost #(orig_cost + Decimal(sell_txn['fee']))
            total_cost += orig_cost
            net_proceeds = Decimal(sell_txn['total']) # - Decimal(sell_txn['fee'])
            total_proceeds += net_proceeds
            total_gains += cap_gain
            # Now update the current cost average
            current_cost_average['size'] = Decimal(current_cost_average['size']) - Decimal(sell_txn['size'])
            if current_cost_average['size'] ==  0:
                current_cost_average = None
            elif current_cost_average['size'] < 0:
                print("UNEXPECTED: Somehow the size of the sell was bigger than the buy")
                sys.exit(1)
                # this can happen if you buy + buy + buy + buy and then one big sell. :( Need  to handle this or just do this manually.
            transaction_details = {}
            transaction_details["token"] = token
            transaction_details["purch_date"] = transaction_date
            transaction_details["sell_date"] = sell_txn['created at']
            transaction_details["size"] = sell_size
            transaction_details["cost_with_fee"] = orig_cost
            transaction_details["net_proceeds"] = net_proceeds
            transaction_details["gain"] = cap_gain
            all_sell_orders.append(transaction_details)
            
        print("Finished calculating sells for: " + token)
        if current_cost_average is not None:
            if transaction_date == 'Various':
                remaining_portion_of_lot = next_buy.copy()
                remaining_portion_of_lot["size"] = total_size_of_buys - Decimal(sell_txn['size'])
                remaining_portion_of_lot['fee'] = 'factored into total'
                remaining_portion_of_lot['total'] = next_cost_average["cost_per_share"] * remaining_portion_of_lot["size"] * -1 # buys are negative
                remaining_portion_of_lot['partial_lot'] = True
                extra_buys.append(remaining_portion_of_lot)

        # if there are unprocessed buys, keep track of these as they will be needed for next year's taxes
        while buy_index < len(token_dict["BUY"]):
            extra_buys.append(token_dict["BUY"][buy_index])
            buy_index +=1

    if extra_buys:
        print()
        print("------------------")
        print("There were additional purchases without a corresponding SELL in the input file.")
        print("These have been saved to: " + args.unsold_lots_file)
        print("You may want to put these into next year's fills list; and in some cases where a partial lot was sold, you will want to replace entries in next year's file with entries from this file")
        with open(args.unsold_lots_file, "w", newline="") as unsold_out:
            unsold_out.write(EXPECTED_HEADER + os.linesep)
            for buy in extra_buys:
                if 'partial_lot' in buy:
                    continue
                for field in EXPECTED_HEADER.split(","):
                    unsold_out.write(str(buy[field]) + ",")
                unsold_out.write(os.linesep)

        with open(args.partially_sold_lots_file, "w", newline="") as partial_lots_out:
            partial_lots_out.write(EXPECTED_HEADER + os.linesep)
            for buy in extra_buys:
                if 'partial_lot' not in buy:
                    continue
                for field in EXPECTED_HEADER.split(","):
                    partial_lots_out.write(str(buy[field]) + ",")
                partial_lots_out.write(os.linesep)
    
    print("TOTAL cost: " + str(total_cost))
    print("TOTAL proceeds: " + str(total_proceeds))
    print("TOTAL gains: " + str(total_gains))
    with open(args.output_file, "w", newline="") as out:
        out.write(",".join(OUTPUT_HEADER))
        out.write(os.linesep)
        for sell_order in all_sell_orders:
            for field in OUTPUT_HEADER:
                out.write(str(sell_order[field]))
                if field != OUTPUT_HEADER[-1]:
                    out.write(",")
            out.write(os.linesep)

if __name__=="__main__":
    main()
