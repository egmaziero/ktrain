from .imports import *
from . import utils as U



__all__ = ['NBSVM']


class Classifier:
    def __init__(self, model=None):
        """
        instantiate a classifier with an optional previously-saved model
        """
        self.model = None

    @classmethod
    def texts_from_folder(cls, folder_path, 
                          subfolders=None, 
                          shuffle=True,
                          encoding=None):
        """
        load text files from folder

        Args:
          folder_path(str): path to folder containing documents
                            The supplied folder should contain a subfolder
                            for each category, which will be used as the class label
          subfolders(list): list of subfolders under folder_path to consider
                            Example: If folder_path contains subfolders pos, neg, and 
                            unlabeled, then unlabeled folder can be ignored by
                            setting subfolders=['pos', 'neg']
          shuffle(bool):  If True, list of texts will be shuffled
          encoding(str): encoding to use.  default:None (auto-detected)
        Returns:
          tuple: (texts, labels, label_names)
        """
        bunch = load_files(folder_path, categories=subfolders, shuffle=shuffle)
        texts = bunch.data
        labels = bunch.target
        label_names = bunch.target_names
        #print('target names:')
        #for idx, label_name in enumerate(bunch.target_names):
            #print('\t%s:%s' % (idx, label_name))

        # decode based on supplied encoding
        if encoding is None:
            encoding = U.detect_encoding(texts)
            if encoding != 'utf-8':
                print('detected encoding: %s' % (encoding))

        try:
            texts = [text.decode(encoding) for text in texts]
        except:
            print('Decoding with %s failed 1st attempt - using %s with skips' % (encoding,
                                                                                 encoding))
            texts = U.decode_by_line(texts, encoding=encoding)
        return (texts, labels, label_names)



    @classmethod
    def texts_from_csv(cls, csv_filepath, text_column='text', label_column='label',
                       sep=',', encoding=None):
        """
        load text files from csv file
        CSV should have at least two columns.
        Example:
        Text               | Label
        I love this movie. | positive
        I hated this movie.| negative


        Args:
          csv_filepath(str): path to CSV file
          text_column(str): name of column containing the texts. default:'text'
          label_column(str): name of column containing the labels in string format
                             default:'label'
          sep(str): character that separates columns in CSV. default:','
          encoding(str): encoding to use. default:None (auto-detected)
        Returns:
          tuple: (texts, labels, label_names)
        """
        if encoding is None:
            with open(csv_filepath, 'rb') as f:
                encoding = U.detect_encoding([f.read()])
                if encoding != 'utf-8':
                    print('detected encoding: %s (if wrong, set manually)' % (encoding))
        df = pd.read_csv(csv_filepath, encoding=encoding, sep=sep)
        texts = df[text_column].fillna('fillna').values
        labels = df[label_column].values
        le = LabelEncoder()
        le.fit(labels)
        labels = le.transform(labels)
        return (texts, labels, le.classes_)


    def fit(self, x_train, y_train, ctype='nbsvm'):
        """
        train a classifier
        Args:
          x_train(list or np.ndarray):  training texts
          y_train(np.ndarray):  training labels
          ctype(str):  Either 'logreg' or 'nbsvm'
        """

        lang = U.detect_lang(x_train)
        if U.is_chinese(lang):
            token_pattern = r'(?u)\b\w+\b'
            x_train = U.split_chinese(x_train)
        else:
            token_pattern = r'\w+|[%s]' % string.punctuation
        if ctype == 'nbsvm':
            clf = NBSVM(C=0.01, alpha=0.75, beta=0.25, fit_intercept=False)
        else:
            clf = LogisticRegression(C=0.1, dual=True)
        self.model = Pipeline([ ('vect', CountVectorizer(ngram_range=(1,3), binary=True, token_pattern=token_pattern)),
                              ('clf', clf) ])
        self.model.fit(x_train, y_train)
        return self


    def predict(self, x_test):
        """
        make predictions on text data
        Args:
          x_test(list or np.ndarray or str): array of texts on which to make predictions or a string representing text
        """

        if isinstance(x_test, str): x_test = [x_test]
        lang = U.detect_lang(x_test)
        if U.is_chinese(lang): x_test = U.split_chinese(x_test)
        if self.model is None: raise ValueError('model is None - call fit or load to set the model')
        predicted = self.model.predict(x_test)
        if len(predicted) == 1: predicted = predicted[0]
        return predicted


    def evaluate(self, x_test, y_test):
        """
        evaluate
        Args:
          x_test(list or np.ndarray):  training texts
          y_test(np.ndarray):  training labels
        """
        predicted = self.predict(x_test)
        return np.mean(predicted == y_test)


    def save(self, filename):
        """
        save model
        """
        dump(self.model, filename)


    def load(self, filename):
        """
        load model
        """
        self.model = load(filename)







class NBSVM(BaseEstimator, LinearClassifierMixin, SparseCoefMixin):

    def __init__(self, alpha=1, C=1, beta=0.25, fit_intercept=False):
        self.alpha = alpha
        self.C = C
        self.beta = beta
        self.fit_intercept = fit_intercept

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        if len(self.classes_) == 2:
            coef_, intercept_ = self._fit_binary(X, y)
            self.coef_ = coef_
            self.intercept_ = intercept_
        else:
            coef_, intercept_ = zip(*[
                self._fit_binary(X, y == class_)
                for class_ in self.classes_
            ])
            self.coef_ = np.concatenate(coef_)
            self.intercept_ = np.array(intercept_).flatten()
        return self

    def _fit_binary(self, X, y):
        p = np.asarray(self.alpha + X[y == 1].sum(axis=0)).flatten()
        q = np.asarray(self.alpha + X[y == 0].sum(axis=0)).flatten()
        r = np.log(p/np.abs(p).sum()) - np.log(q/np.abs(q).sum())
        b = np.log((y == 1).sum()) - np.log((y == 0).sum())

        if isinstance(X, spmatrix):
            indices = np.arange(len(r))
            r_sparse = coo_matrix(
                (r, (indices, indices)),
                shape=(len(r), len(r))
            )
            X_scaled = X * r_sparse
        else:
            X_scaled = X * r

        lsvc = LinearSVC(
            C=self.C,
            fit_intercept=self.fit_intercept,
            max_iter=10000
        ).fit(X_scaled, y)

        mean_mag =  np.abs(lsvc.coef_).mean()

        coef_ = (1 - self.beta) * mean_mag * r + \
                self.beta * (r * lsvc.coef_)

        intercept_ = (1 - self.beta) * mean_mag * b + \
                     self.beta * lsvc.intercept_

        return coef_, intercept_



# hyperparam search for NBSVM
# # hyperparameter tuning
# parameters = {
# #               'clf__C': (1e0, 1e-1, 1e-2),
#               'clf__alpha': (0.1, 0.2, 0.4, 0.5, 0.75, 0.9, 1.0),
# #               'clf__fit_intercept': (True, False),
# #                'clf__beta' : (0.1, 0.25, 0.5, 0.9)


# }
# gs_clf = GridSearchCV(text_clf, parameters, n_jobs=-1)
# #gs_clf = gs_clf.fit(X_train[:5000], y_train[:5000])
# gs_clf = gs_clf.fit(X_train, y_train)