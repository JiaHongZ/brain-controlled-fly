import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.eeg_decoder import prepare

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Download official BNCI EEG and prepare a session-held-out CSP/LDA replay.')
    parser.add_argument('--force',action='store_true',help='Refit from cached raw public EEG')
    args=parser.parse_args()
    _,metrics=prepare(force=args.force)
    print(f'Accuracy: {metrics["accuracy"]:.1%}; confusion matrix: {metrics["confusion_matrix"]}')
