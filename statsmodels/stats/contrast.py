from statsmodels.compat.python import range
import numpy as np
from scipy.stats import f as fdist
from scipy.stats import t as student_t
from scipy import stats
from statsmodels.tools.tools import clean0, fullrank
from statsmodels.compat.numpy import np_matrix_rank


#TODO: should this be public if it's just a container?
class ContrastResults(object):
    """
    Container class for looking at contrasts of coefficients in a model.

    The class does nothing, it is a container for the results from T and F.
    """

    def __init__(self, t=None, F=None, sd=None, effect=None, df_denom=None,
                 df_num=None, alpha=0.05, **kwds):

        self.effect = effect  # Let it be None for F
        if F is not None:
            self.distribution = 'F'
            self.fvalue = F
            self.df_denom = df_denom
            self.df_num = df_num
            self.dist = fdist
            self.dist_args = (df_num, df_denom)
            self.pvalue = fdist.sf(F, df_num, df_denom)
        elif t is not None:
            self.distribution = 't'
            self.tvalue = t
            self.statistic = t  # generic alias
            self.sd = sd
            self.df_denom = df_denom
            self.dist = student_t
            self.dist_args = (df_denom,)
            self.pvalue = self.dist.sf(np.abs(t), df_denom) * 2
        elif 'statistic' in kwds:
            # TODO: currently targeted to normal distribution, and chi2
            self.distribution = kwds['distribution']
            self.statistic = kwds['statistic']
            self.tvalue = value = kwds['statistic']  # keep alias
            # TODO: for results instance we decided to use tvalues also for normal
            self.sd = sd
            self.dist = getattr(stats, self.distribution)
            self.dist_args = ()
            if self.distribution is 'chi2':
                self.pvalue = self.dist.sf(self.statistic, df_denom)
            else:
                "normal"
                self.pvalue = self.dist.sf(np.abs(value)) * 2

        # cleanup
        # should we return python scalar?
        self.pvalue = np.squeeze(self.pvalue)


    def conf_int(self, alpha=0.05):
        if self.effect is not None:
            # confidence intervals
            q = self.dist.ppf(1 - alpha / 2., *self.dist_args)
            lower = self.effect - q * self.sd
            upper = self.effect + q * self.sd
            return np.column_stack((lower, upper))
        else:
            raise NotImplementedError('Confidence Interval not available')


    def __array__(self):
        if hasattr(self, "fvalue"):
            return self.fvalue
        else:
            return self.tvalue

    def __str__(self):
        return self.summary().__str__()


    def __repr__(self):
        return str(self.__class__) + '\n' + self.__str__()


    def summary(self, xname=None, alpha=0.05, title=None):
        if self.effect is not None:
            # TODO: should also add some extra information, e.g. robust cov ?
            # TODO: can we infer names for constraints, xname in __init__ ?
            if title is None:
                title = 'Test for Constraints'
            elif title == '':
                # don't add any title,
                # I think SimpleTable skips on None - check
                title = None
            # we have everything for a params table
            use_t = (self.distribution == 't')
            yname='constraints' # Not used in params_frame
            if xname is None:
                xname = ['c%d'%ii for ii in range(len(self.effect))]
            from statsmodels.iolib.summary import summary_params
            pvalues = np.atleast_1d(self.pvalue)
            summ = summary_params((self, self.effect, self.sd, self.statistic,
                                   pvalues, self.conf_int(alpha)),
                                  yname=yname, xname=xname, use_t=use_t,
                                  title=title)
            return summ
        elif hasattr(self, 'fvalue'):
            # TODO: create something nicer for these casee
            return '<F test: F=%s, p=%s, df_denom=%d, df_num=%d>' % \
                   (repr(self.fvalue), self.pvalue, self.df_denom, self.df_num)
        else:
            # generic
            return '<Wald test: statistic=%s, p-value=%s>' % \
                   (self.statistic, self.pvalue)


    def summary_frame(self, xname=None, alpha=0.05):
        if self.effect is not None:
            # we have everything for a params table
            use_t = (self.distribution == 't')
            yname='constraints'  # Not used in params_frame
            if xname is None:
                xname = ['c%d'%ii for ii in range(len(self.effect))]
            from statsmodels.iolib.summary import summary_params_frame
            summ = summary_params_frame((self, self.effect, self.sd,
                                         self.statistic,self.pvalue,
                                         self.conf_int(alpha)), yname=yname,
                                         xname=xname, use_t=use_t)
            return summ
        else:
            # TODO: create something nicer
            raise NotImplementedError('only available for t and z')



class Contrast(object):
    """
    This class is used to construct contrast matrices in regression models.

    They are specified by a (term, design) pair.  The term, T, is a linear
    combination of columns of the design matrix. The matrix attribute of
    Contrast is a contrast matrix C so that

    colspan(dot(D, C)) = colspan(dot(D, dot(pinv(D), T)))

    where pinv(D) is the generalized inverse of D. Further, the matrix

    Tnew = dot(C, D)

    is full rank. The rank attribute is the rank of

    dot(D, dot(pinv(D), T))

    In a regression model, the contrast tests that E(dot(Tnew, Y)) = 0
    for each column of Tnew.

    Parameters
    ----------
    term ; array-like
    design : array-like

    Attributes
    ----------
    contrast_matrix

    Examples
    ---------
    >>>import numpy.random as R
    >>>import statsmodels.api as sm
    >>>import numpy as np
    >>>R.seed(54321)
    >>>X = R.standard_normal((40,10))

    Get a contrast

    >>>new_term = np.column_stack((X[:,0], X[:,2]))
    >>>c = sm.contrast.Contrast(new_term, X)
    >>>test = [[1] + [0]*9, [0]*2 + [1] + [0]*7]
    >>>np.allclose(c.contrast_matrix, test)
    True

    Get another contrast

    >>>P = np.dot(X, np.linalg.pinv(X))
    >>>resid = np.identity(40) - P
    >>>noise = np.dot(resid,R.standard_normal((40,5)))
    >>>new_term2 = np.column_stack((noise,X[:,2]))
    >>>c2 = Contrast(new_term2, X)
    >>>print c2.contrast_matrix
    [ -1.26424750e-16   8.59467391e-17   1.56384718e-01  -2.60875560e-17
  -7.77260726e-17  -8.41929574e-18  -7.36359622e-17  -1.39760860e-16
   1.82976904e-16  -3.75277947e-18]

    Get another contrast

    >>>zero = np.zeros((40,))
    >>>new_term3 = np.column_stack((zero,X[:,2]))
    >>>c3 = sm.contrast.Contrast(new_term3, X)
    >>>test2 = [0]*2 + [1] + [0]*7
    >>>np.allclose(c3.contrast_matrix, test2)
    True

    """
    def _get_matrix(self):
        """
        Gets the contrast_matrix property
        """
        if not hasattr(self, "_contrast_matrix"):
            self.compute_matrix()
        return self._contrast_matrix

    contrast_matrix = property(_get_matrix)

    def __init__(self, term, design):
        self.term = np.asarray(term)
        self.design = np.asarray(design)

    def compute_matrix(self):
        """
        Construct a contrast matrix C so that

        colspan(dot(D, C)) = colspan(dot(D, dot(pinv(D), T)))

        where pinv(D) is the generalized inverse of D=design.
        """

        T = self.term
        if T.ndim == 1:
            T = T[:,None]

        self.T = clean0(T)
        self.D = self.design
        self._contrast_matrix = contrastfromcols(self.T, self.D)
        try:
            self.rank = self.matrix.shape[1]
        except:
            self.rank = 1

#TODO: fix docstring after usage is settled
def contrastfromcols(L, D, pseudo=None):
    """
    From an n x p design matrix D and a matrix L, tries
    to determine a p x q contrast matrix C which
    determines a contrast of full rank, i.e. the
    n x q matrix

    dot(transpose(C), pinv(D))

    is full rank.

    L must satisfy either L.shape[0] == n or L.shape[1] == p.

    If L.shape[0] == n, then L is thought of as representing
    columns in the column space of D.

    If L.shape[1] == p, then L is thought of as what is known
    as a contrast matrix. In this case, this function returns an estimable
    contrast corresponding to the dot(D, L.T)

    Note that this always produces a meaningful contrast, not always
    with the intended properties because q is always non-zero unless
    L is identically 0. That is, it produces a contrast that spans
    the column space of L (after projection onto the column space of D).

    Parameters
    ----------
    L : array-like
    D : array-like
    """
    L = np.asarray(L)
    D = np.asarray(D)

    n, p = D.shape

    if L.shape[0] != n and L.shape[1] != p:
        raise ValueError("shape of L and D mismatched")

    if pseudo is None:
        pseudo = np.linalg.pinv(D)    # D^+ \approx= ((dot(D.T,D))^(-1),D.T)

    if L.shape[0] == n:
        C = np.dot(pseudo, L).T
    else:
        C = L
        C = np.dot(pseudo, np.dot(D, C.T)).T

    Lp = np.dot(D, C.T)

    if len(Lp.shape) == 1:
        Lp.shape = (n, 1)

    if np_matrix_rank(Lp) != Lp.shape[1]:
        Lp = fullrank(Lp)
        C = np.dot(pseudo, Lp).T

    return np.squeeze(C)
