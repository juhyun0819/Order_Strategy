"""
컬럼 검증 유틸리티 모듈
단일 책임: 데이터프레임의 필수 컬럼 존재 여부 검증
"""
import pandas as pd
from typing import Set, List, Tuple, Optional


class ColumnValidator:
    """데이터프레임 컬럼 검증을 담당하는 클래스"""
    
    # 필수 컬럼 정의 (상수)
    REQUIRED_COLUMNS = {'품명', '칼라', '사이즈', '실판매', '현재고', '미송잔량'}
    
    @classmethod
    def validate_required_columns(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        필수 컬럼 존재 여부 검증
        
        Args:
            df: 검증할 데이터프레임
            
        Returns:
            Tuple[bool, List[str]]: (검증 통과 여부, 누락된 컬럼 목록)
        """
        if df.empty:
            return False, list(cls.REQUIRED_COLUMNS)
        
        missing_columns = list(cls.REQUIRED_COLUMNS - set(df.columns))
        is_valid = len(missing_columns) == 0
        
        return is_valid, missing_columns
    
    @classmethod
    def validate_analysis_columns(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        분석에 필요한 최소 컬럼 검증 (품명, 칼라)
        
        Args:
            df: 검증할 데이터프레임
            
        Returns:
            Tuple[bool, List[str]]: (검증 통과 여부, 누락된 컬럼 목록)
        """
        if df.empty:
            return False, ['품명', '칼라']
        
        analysis_columns = {'품명', '칼라'}
        missing_columns = list(analysis_columns - set(df.columns))
        is_valid = len(missing_columns) == 0
        
        return is_valid, missing_columns
    
    @classmethod
    def get_available_columns(cls, df: pd.DataFrame) -> Set[str]:
        """
        데이터프레임에서 사용 가능한 컬럼 목록 반환
        
        Args:
            df: 확인할 데이터프레임
            
        Returns:
            Set[str]: 사용 가능한 컬럼 목록
        """
        return set(df.columns) if not df.empty else set()
    
    @classmethod
    def get_missing_columns_message(cls, missing_columns: List[str]) -> str:
        """
        누락된 컬럼에 대한 사용자 친화적 메시지 생성
        
        Args:
            missing_columns: 누락된 컬럼 목록
            
        Returns:
            str: 사용자 친화적 오류 메시지
        """
        if not missing_columns:
            return ""
        
        # 컬럼명을 한국어로 매핑
        column_names = {
            '품명': '품명',
            '칼라': '칼라(색상)',
            '사이즈': '사이즈',
            '실판매': '실판매',
            '현재고': '현재고',
            '미송잔량': '미송잔량'
        }
        
        korean_columns = [column_names.get(col, col) for col in missing_columns]
        
        if len(korean_columns) == 1:
            return f"필수 컬럼 '{korean_columns[0]}'이(가) 누락되었습니다. 엑셀 파일의 컬럼명을 확인해주세요."
        else:
            columns_str = "', '".join(korean_columns)
            return f"필수 컬럼 '{columns_str}'이(가) 누락되었습니다. 엑셀 파일의 컬럼명을 확인해주세요."
    
    @classmethod
    def get_required_columns_help_message(cls) -> str:
        """
        필수 컬럼에 대한 도움말 메시지 생성
        
        Returns:
            str: 도움말 메시지
        """
        return "필수 컬럼: 품명, 칼라(색상), 사이즈, 실판매, 현재고, 미송잔량"
