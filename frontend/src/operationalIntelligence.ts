export type OperationalMetric={key:string;label:string;value:number|null;unit:string;population:string;status:string};
export function displayNumber(value:number|null):string {
  return value===null || !Number.isFinite(value)?'Não disponível':new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(value);
}
export function displayDuration(seconds:number|null):string {
  if(seconds===null || !Number.isFinite(seconds) || seconds<0)return 'Não disponível';
  if(seconds<60)return `${displayNumber(seconds)} s`;
  if(seconds<3600)return `${displayNumber(seconds/60)} min`;
  if(seconds<86400)return `${displayNumber(seconds/3600)} h`;
  return `${displayNumber(seconds/86400)} dias`;
}
