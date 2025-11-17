from src import strategy_manager
from src.strategies import (
    evaluate_golden_cross, 
    evaluate_rsi_dip, 
    evaluate_macd_crossover, 
    evaluate_bollinger_breakout, 
    evaluate_awesome_oscillator, 
    evaluate_ml_prediction
)

BASE_STRATEGIES = {
    'evaluate_golden_cross': strategy_manager.Strategy('Golden Cross', evaluate_golden_cross, {}, 1.0),
    'evaluate_rsi_dip': strategy_manager.Strategy('RSI Dip', evaluate_rsi_dip, {}, 0.8),
    'evaluate_macd_crossover': strategy_manager.Strategy('MACD Crossover', evaluate_macd_crossover, {}, 0.9),
    'evaluate_bollinger_breakout': strategy_manager.Strategy('Bollinger Breakout', evaluate_bollinger_breakout, {}, 0.85),
    'evaluate_awesome_oscillator': strategy_manager.Strategy('Awesome Oscillator', evaluate_awesome_oscillator, {}, 0.8),
    'evaluate_ml_prediction': strategy_manager.Strategy('ML Prediction', evaluate_ml_prediction, {}, 0.7, is_active=True)
}
