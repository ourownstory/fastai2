# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/30_text.core.ipynb (unless otherwise specified).

__all__ = ['UNK', 'PAD', 'BOS', 'EOS', 'FLD', 'TK_REP', 'TK_WREP', 'TK_UP', 'TK_MAJ', 'spec_add_spaces',
           'rm_useless_spaces', 'replace_rep', 'replace_wrep', 'fix_html', 'replace_all_caps', 'replace_maj',
           'lowercase', 'replace_space', 'BaseTokenizer', 'SpacyTokenizer', 'TokenizeBatch', 'tokenize1',
           'parallel_tokenize', 'fn_counter_pkl', 'fn_lengths_pkl', 'tokenize_folder', 'read_tokenized_file',
           'tokenize_files', 'tokenize_df', 'tokenize_csv', 'load_tokenized_csv', 'get_tokenizer', 'Tokenizer',
           'eu_langs', 'SentencePieceTokenizer']

# Cell
from ..torch_basics import *
from ..data.all import *

# Cell
import spacy,html
from spacy.symbols import ORTH

# Cell
#special tokens
UNK, PAD, BOS, EOS, FLD, TK_REP, TK_WREP, TK_UP, TK_MAJ = "xxunk xxpad xxbos xxeos xxfld xxrep xxwrep xxup xxmaj".split()

# Cell
_re_spec = re.compile(r'([/#\\])')

def spec_add_spaces(t):
    "Add spaces around / and #"
    return _re_spec.sub(r' \1 ', t)

# Cell
_re_space = re.compile(' {2,}')

def rm_useless_spaces(t):
    "Remove multiple spaces"
    return _re_space.sub(' ', t)

# Cell
_re_rep = re.compile(r'(\S)(\1{2,})')

def replace_rep(t):
    "Replace repetitions at the character level: cccc -- TK_REP 4 c"
    def _replace_rep(m):
        c,cc = m.groups()
        return f' {TK_REP} {len(cc)+1} {c} '
    return _re_rep.sub(_replace_rep, t)

# Cell
_re_wrep = re.compile(r'(?:\s|^)(\w+)\s+((?:\1\s+)+)\1(\s|\W|$)')

# Cell
def replace_wrep(t):
    "Replace word repetitions: word word word word -- TK_WREP 4 word"
    def _replace_wrep(m):
        c,cc,e = m.groups()
        return f' {TK_WREP} {len(cc.split())+2} {c} {e}'
    return _re_wrep.sub(_replace_wrep, t)

# Cell
def fix_html(x):
    "Various messy things we've seen in documents"
    x = x.replace('#39;', "'").replace('amp;', '&').replace('#146;', "'").replace('nbsp;', ' ').replace(
        '#36;', '$').replace('\\n', "\n").replace('quot;', "'").replace('<br />', "\n").replace(
        '\\"', '"').replace('<unk>',UNK).replace(' @.@ ','.').replace(' @-@ ','-').replace('...',' …')
    return html.unescape(x)

# Cell
_re_all_caps = re.compile(r'(\s|^)([A-Z]+[^a-z\s]*)(?=(\s|$))')

# Cell
def replace_all_caps(t):
    "Replace tokens in ALL CAPS by their lower version and add `TK_UP` before."
    def _replace_all_caps(m):
        tok = f'{TK_UP} ' if len(m.groups()[1]) > 1 else ''
        return f"{m.groups()[0]}{tok}{m.groups()[1].lower()}"
    return _re_all_caps.sub(_replace_all_caps, t)

# Cell
_re_maj = re.compile(r'(\s|^)([A-Z][^A-Z\s]*)(?=(\s|$))')

# Cell
def replace_maj(t):
    "Replace tokens in ALL CAPS by their lower version and add `TK_UP` before."
    def _replace_maj(m):
        tok = f'{TK_MAJ} ' if len(m.groups()[1]) > 1 else ''
        return f"{m.groups()[0]}{tok}{m.groups()[1].lower()}"
    return _re_maj.sub(_replace_maj, t)

# Cell
def lowercase(t, add_bos=True, add_eos=False):
    "Converts `t` to lowercase"
    return (f'{BOS} ' if add_bos else '') + t.lower().strip() + (f' {EOS}' if add_eos else '')

# Cell
def replace_space(t):
    "Replace embedded spaces in a token with unicode line char to allow for split/join"
    return t.replace(' ', '▁')

# Cell
defaults.text_spec_tok = [UNK, PAD, BOS, EOS, FLD, TK_REP, TK_WREP, TK_UP, TK_MAJ]
defaults.text_proc_rules = [fix_html, replace_rep, replace_wrep, spec_add_spaces, rm_useless_spaces,
                            replace_all_caps, replace_maj, lowercase]
defaults.text_postproc_rules = [replace_space]

# Cell
class BaseTokenizer():
    "Basic tokenizer that just splits on spaces"
    def __init__(self, split_char=' ', **kwargs): self.split_char=split_char
    def __call__(self, items): return (t.split(self.split_char) for t in items)

# Cell
class SpacyTokenizer():
    "Spacy tokenizer for `lang`"
    def __init__(self, lang='en', special_toks=None, buf_sz=5000):
        special_toks = ifnone(special_toks, defaults.text_spec_tok)
        nlp = spacy.blank(lang, disable=["parser", "tagger", "ner"])
        for w in special_toks: nlp.tokenizer.add_special_case(w, [{ORTH: w}])
        self.pipe,self.buf_sz = nlp.pipe,buf_sz

    def __call__(self, items):
        return (L(doc).attrgot('text') for doc in self.pipe(items, batch_size=self.buf_sz))

# Cell
class TokenizeBatch:
    "A wrapper around `tok_func` to apply `rules` and tokenize in parallel"
    def __init__(self, tok_func=SpacyTokenizer, rules=None, post_rules=None, **tok_kwargs ):
        self.rules = L(ifnone(rules, defaults.text_proc_rules))
        self.post_f = compose(*L(ifnone(post_rules, defaults.text_postproc_rules)))
        self.tok = tok_func(**tok_kwargs)

    def __call__(self, batch):
        return (L(o).map(self.post_f) for o in self.tok(maps(*self.rules, batch)))

# Cell
def tokenize1(text, tok_func=SpacyTokenizer, rules=None, post_rules=None, **tok_kwargs):
    "Tokenize one `text` with an instance of `tok_func` and some `rules`"
    return first(TokenizeBatch(tok_func, rules, post_rules, **tok_kwargs)([text]))

# Cell
def parallel_tokenize(items, tok_func, rules, as_gen=False, n_workers=defaults.cpus, **tok_kwargs):
    "Calls a potential setup on `tok_func` before launching `TokenizeBatch` in parallel"
    if hasattr(tok_func, 'setup'): tok_kwargs = tok_func(**tok_kwargs).setup(items, rules)
    return parallel_gen(TokenizeBatch, items, as_gen=as_gen, tok_func=tok_func,
                        rules=rules, n_workers=n_workers, **tok_kwargs)

# Cell
fn_counter_pkl = 'counter.pkl'
fn_lengths_pkl = 'lengths.pkl'

# Cell
def tokenize_folder(path, extensions=None, folders=None, output_dir=None, n_workers=defaults.cpus,
                    rules=None, tok_func=SpacyTokenizer, encoding='utf8', **tok_kwargs):
    "Tokenize text files in `path` in parallel using `n_workers`"
    path,extensions = Path(path),ifnone(extensions, ['.txt'])
    fnames = get_files(path, extensions=extensions, recurse=True, folders=folders)
    output_dir = Path(ifnone(output_dir, path.parent/f'{path.name}_tok'))
    rules = partial(Path.read, encoding=encoding) + L(ifnone(rules, defaults.text_proc_rules.copy()))

    lengths,counter = {},Counter()
    for i,tok in parallel_tokenize(fnames, tok_func, rules, as_gen=True, n_workers=n_workers, **tok_kwargs):
        out = output_dir/fnames[i].relative_to(path)
        out.write(' '.join(tok))
        lengths[str(fnames[i].relative_to(path))] = len(tok)
        counter.update(tok)

    (output_dir/fn_lengths_pkl).save(lengths)
    (output_dir/fn_counter_pkl).save(counter)

# Cell
def read_tokenized_file(f): return L(f.read().split(' '))

# Cell
def tokenize_files(files, output_dir, output_names=None, n_workers=defaults.cpus, rules=None, tok_func=SpacyTokenizer,
                   encoding='utf8', **tok_kwargs):
    "Tokenize text `files` in parallel using `n_workers`"
    if output_names is None: output_names = L(f'{i}.txt' for i in range_of(files))
    output_dir = Path(output_dir)
    rules = partial(Path.read, encoding=encoding) + L(ifnone(rules, defaults.text_proc_rules.copy()))

    lengths = (output_dir/fn_lengths_pkl).load() if (output_dir/fn_lengths_pkl).exists() else {}
    counter = (output_dir/fn_counter_pkl).load() if (output_dir/fn_counter_pkl).exists() else Counter()
    for i,tok in parallel_tokenize(files, tok_func, rules, as_gen=True, n_workers=n_workers, **tok_kwargs):
        out = output_dir/output_names[i]
        out.write(' '.join(tok))
        lengths[output_names[i]] = len(tok)
        counter.update(tok)

    (output_dir/fn_lengths_pkl).save(lengths)
    (output_dir/fn_counter_pkl).save(counter)

# Cell
def _join_texts(df, mark_fields=False):
    "Join texts in row `idx` of `df`, marking each field with `FLD` if `mark_fields=True`"
    text_col = (f'{FLD} {1} ' if mark_fields else '' ) + df.iloc[:,0].astype(str)
    for i in range(1,len(df.columns)):
        text_col += (f' {FLD} {i+1} ' if mark_fields else ' ') + df.iloc[:,i].astype(str)
    return text_col.values

# Cell
def tokenize_df(df, text_cols, n_workers=defaults.cpus, rules=None, mark_fields=None,
                tok_func=SpacyTokenizer, res_col_name="text", **tok_kwargs):
    "Tokenize texts in `df[text_cols]` in parallel using `n_workers`"
    text_cols = [df.columns[c] if isinstance(c, int) else c for c in L(text_cols)]
    #mark_fields defaults to False if there is one column of texts, True if there are multiple
    if mark_fields is None: mark_fields = len(text_cols)>1
    rules = L(ifnone(rules, defaults.text_proc_rules.copy()))
    texts = _join_texts(df[text_cols], mark_fields=mark_fields)
    outputs = L(parallel_tokenize(texts, tok_func, rules, n_workers=n_workers, **tok_kwargs)
               ).sorted().itemgot(1)

    other_cols = df.columns[~df.columns.isin(text_cols)]
    res = df[other_cols].copy()
    res[res_col_name] = outputs
    res[f'{res_col_name}_length'] = [len(o) for o in outputs]
    return res,Counter(outputs.concat())

# Cell
def tokenize_csv(fname, text_cols, outname=None, n_workers=4, rules=None, mark_fields=None,
                 tok_func=SpacyTokenizer, header='infer', chunksize=50000, **tok_kwargs):
    "Tokenize texts in the `text_cols` of the csv `fname` in parallel using `n_workers`"
    df = pd.read_csv(fname, header=header, chunksize=chunksize)
    outname = Path(ifnone(outname, fname.parent/f'{fname.stem}_tok.csv'))
    cnt = Counter()

    for i,dfp in enumerate(df):
        out,c = tokenize_df(dfp, text_cols, n_workers=n_workers, rules=rules,
                            mark_fields=mark_fields, tok_func=tok_func, **tok_kwargs)
        out.text = out.text.str.join(' ')
        out.to_csv(outname, header=(None,header)[i==0], index=False, mode=('a','w')[i==0])
        cnt.update(c)

    outname.with_suffix('.pkl').save(cnt)

# Cell
def load_tokenized_csv(fname):
    "Utility function to quickly load a tokenized csv ans the corresponding counter"
    fname = Path(fname)
    out = pd.read_csv(fname)
    for txt_col in out.columns[1:-1]:
        out[txt_col] = out[txt_col].str.split(' ')
    return out,fname.with_suffix('.pkl').load()

# Cell
def get_tokenizer(tok_func=SpacyTokenizer, **kwargs):
    sign = str(inspect.signature(tok_func))
    for k in list(kwargs.keys()):
        if k not in sign: kwargs.pop(k)
    return tok_func(**kwargs)

# Cell
class Tokenizer(Transform):
    input_types = (str, list, L, tuple, Path)
    def __init__(self, tokenizer, rules=None, counter=None, lengths=None, mode=None):
        store_attr(self, 'tokenizer,counter,lengths,mode')
        self.rules = defaults.text_proc_rules if rules is None else rules

    @classmethod
    @delegates(tokenize_df, keep=True)
    def from_df(cls, text_cols, tok_func=SpacyTokenizer, rules=None, **kwargs):
        res = cls(get_tokenizer(tok_func, **kwargs), rules=rules, mode='df')
        res.text_cols,res.kwargs,res.train_setup = text_cols,merge({'tok_func': tok_func}, kwargs),False
        return res

    @classmethod
    @delegates(tokenize_folder, keep=True)
    def from_folder(cls, path, tok_func=SpacyTokenizer, rules=None, **kwargs):
        path = Path(path)
        output_dir = Path(ifnone(kwargs.get('output_dir'), path.parent/f'{path.name}_tok'))
        if not output_dir.exists(): tokenize_folder(path, rules=rules, **kwargs)
        res = cls(get_tokenizer(tok_func, **kwargs), counter=(output_dir/fn_counter_pkl).load(),
                  lengths=(output_dir/fn_lengths_pkl).load(), rules=rules, mode='folder')
        res.path,res.output_dir = path,output_dir
        return res

    def setups(self, dsets):
        if not self.mode == 'df' or not isinstance(dsets.items, pd.DataFrame): return
        dsets.items,count = tokenize_df(dsets.items, self.text_cols, rules=self.rules, **self.kwargs)
        if self.counter is None: self.counter = count
        return dsets

    def encodes(self, o:Path):
        if self.mode=='folder' and str(o).startswith(str(self.path)):
            tok = self.output_dir/o.relative_to(self.path)
            return L(tok.read().split(' '))
        else: return self._tokenize1(o.read())

    def encodes(self, o:str): return self._tokenize1(o)
    def _tokenize1(self, o): return first(self.tokenizer([compose(*self.rules)(o)]))

    def get_lengths(self, items):
        if self.lengths is None: return None
        if self.mode == 'df':
            if isinstance(items, pd.DataFrame) and 'text_lengths' in items.columns: return items['text_length'].values
        if self.mode == 'folder':
            try:
                res = [self.lengths[str(Path(i).relative_to(self.path))] for i in items]
                if len(res) == len(items): return res
            except: return None

# Cell
eu_langs = ["bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "ga", "hr", "hu",
            "it","lt","lv","mt","nl","pl","pt","ro","sk","sl","sv"] # all European langs

# Cell
class SentencePieceTokenizer():#TODO: pass the special tokens symbol to sp
    "Spacy tokenizer for `lang`"
    def __init__(self, lang='en', special_toks=None, sp_model=None, vocab_sz=None, max_vocab_sz=30000,
                 model_type='unigram', char_coverage=None, cache_dir='tmp'):
        try: from sentencepiece import SentencePieceTrainer,SentencePieceProcessor
        except ImportError:
            raise Exception('sentencepiece module is missing: run `pip install sentencepiece`')
        self.sp_model,self.cache_dir = sp_model,Path(cache_dir)
        self.vocab_sz,self.max_vocab_sz,self.model_type = vocab_sz,max_vocab_sz,model_type
        self.char_coverage = ifnone(char_coverage, 0.99999 if lang in eu_langs else 0.9998)
        self.special_toks = ifnone(special_toks, defaults.text_spec_tok)
        if sp_model is None: self.tok = None
        else:
            self.tok = SentencePieceProcessor()
            self.tok.Load(str(sp_model))
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_vocab_sz(self, raw_text_path):
        cnt = Counter()
        with open(raw_text_path, 'r') as f:
            for line in f.readlines():
                cnt.update(line.split())
                if len(cnt)//4 > self.max_vocab_sz: return self.max_vocab_sz
        res = len(cnt)//4
        while res%8 != 0: res+=1
        return res

    def train(self, raw_text_path):
        "Train a sentencepiece tokenizer on `texts` and save it in `path/tmp_dir`"
        from sentencepiece import SentencePieceTrainer
        vocab_sz = self._get_vocab_sz(raw_text_path) if self.vocab_sz is None else self.vocab_sz
        spec_tokens = ['\u2581'+s for s in self.special_toks]
        SentencePieceTrainer.Train(" ".join([
            f"--input={raw_text_path} --vocab_size={vocab_sz} --model_prefix={self.cache_dir/'spm'}",
            f"--character_coverage={self.char_coverage} --model_type={self.model_type}",
            f"--unk_id={len(spec_tokens)} --pad_id=-1 --bos_id=-1 --eos_id=-1",
            f"--user_defined_symbols={','.join(spec_tokens)}"]))
        raw_text_path.unlink()
        return self.cache_dir/'spm.model'

    def setup(self, items, rules):
        if self.tok is not None: return {'sp_model': self.sp_model}
        raw_text_path = self.cache_dir/'texts.out'
        with open(raw_text_path, 'w') as f:
            for t in progress_bar(maps(*rules, items), total=len(items), leave=False):
                f.write(f'{t}\n')
        return {'sp_model': self.train(raw_text_path)}

    def __call__(self, items):
        for t in items: yield self.tok.EncodeAsPieces(t)