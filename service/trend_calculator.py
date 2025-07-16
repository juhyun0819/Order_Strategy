import numpy as np
from scipy import interpolate

class TrendCalculator:
    """LOWESS 기반 추세 계산기"""
    
    def __init__(self, window=7, frac=0.2):
        self.window = window
        self.frac = frac
    
    def _lowess(self, y):
        """LOWESS 스무딩"""
        n = len(y)
        if n < 3:
            return np.array(y)
        
        # 간단한 이동평균 기반 스무딩
        smoothed = np.convolve(y, np.ones(self.window)/self.window, mode='same')
        return smoothed
    
    def lower_trend(self, y):
        """하단 추세선"""
        return self._lowess(y) * 0.8
    
    def upper_trend(self, y):
        """상단 추세선"""
        return self._lowess(y) * 1.2
    
    def mid_trend(self, y):
        """중간 추세선"""
        return self._lowess(y) 