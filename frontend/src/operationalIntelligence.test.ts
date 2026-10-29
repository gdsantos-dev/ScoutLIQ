import { describe,it,expect } from 'vitest';
import { displayNumber,displayDuration } from './operationalIntelligence';
describe('operational measurement display',()=>{
  it('keeps unknown distinct from a measured zero',()=>{
    expect(displayNumber(null)).toBe('Não disponível');expect(displayNumber(0)).toBe('0');
    expect(displayDuration(null)).toBe('Não disponível');expect(displayDuration(0)).toBe('0 s');
  });
  it('formats durations without implying human effort',()=>{
    expect(displayDuration(90)).toBe('1,5 min');expect(displayDuration(7200)).toBe('2 h');expect(displayDuration(172800)).toBe('2 dias');
  });
  it('rejects invalid measurements',()=>{
    expect(displayNumber(Infinity)).toBe('Não disponível');expect(displayDuration(-1)).toBe('Não disponível');
  });
});
