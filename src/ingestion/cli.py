"""CLI for safe bounded inspection and preparing a PaySim sample."""
import argparse,json
from pathlib import Path
import pandas as pd
from src.ingestion.adapters import inspect_csv,prepare_paysim

def main():
    parser=argparse.ArgumentParser(description='Module 1: dataset inspection/preparation')
    parser.add_argument('--dataset',choices=['paysim','banksim'],required=True)
    parser.add_argument('--csv',required=True)
    parser.add_argument('--rows',type=int,default=100000)
    parser.add_argument('--out',help='Optional output CSV; PaySim only')
    args=parser.parse_args()
    if args.rows<1: parser.error('--rows must be positive')
    result=inspect_csv(args.csv,args.dataset,args.rows)
    print(json.dumps(result,indent=2))
    if args.out:
        if args.dataset!='paysim': parser.error('--out currently supports only PaySim')
        df=pd.read_csv(args.csv,nrows=args.rows)
        prepared=prepare_paysim(df)
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        prepared.to_csv(out,index=False)
        print(f'Prepared sample written to {out} ({len(prepared)} rows)')
if __name__=='__main__': main()
