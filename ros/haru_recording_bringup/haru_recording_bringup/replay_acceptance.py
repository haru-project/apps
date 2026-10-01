"""Explicit subscriber arrival acceptance, separate from scheduler deadlines."""
import math


def arrival_acceptance(statistics, maximum_ms=None, p99_ms=None, uncertainty_seconds=0.):
    limits={'max':maximum_ms,'p99':p99_ms}
    for value in limits.values():
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<=0):
            raise ValueError('Arrival limits must be finite and positive')
    if type(uncertainty_seconds) not in (int,float) or not math.isfinite(uncertainty_seconds) or uncertainty_seconds<0:raise ValueError('Clock uncertainty must be finite and nonnegative')
    failures=[]
    for domain,values in statistics.items():
        for metric,limit in limits.items():
            if limit is None:continue
            observed=values.get(metric)
            if observed is None or not math.isfinite(observed) or (observed+uncertainty_seconds)*1000>limit:
                failures.append({'domain':int(domain),'metric':metric,'observed_seconds':observed,'limit_ms':limit})
    if any(value is not None for value in limits.values()) and not statistics:
        failures.append({'error':'No subscriber arrival evidence'})
    return {'enabled':any(value is not None for value in limits.values()),'passed':not failures,
            'limits_ms':limits,'clock_uncertainty_seconds':uncertainty_seconds,'failures':failures,'measurement':'absolute subscriber arrival error'}


def publisher_acceptance(lateness, maximum_ms=None):
    if maximum_ms is not None and (type(maximum_ms) not in (int,float) or not math.isfinite(maximum_ms) or maximum_ms<=0):
        raise ValueError('Publisher lateness limit must be finite and positive')
    valid=bool(lateness) and all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in lateness)
    maximum=max(lateness) if valid else None
    return {'enabled':maximum_ms is not None,'passed':maximum_ms is None or (valid and maximum*1000<=maximum_ms),
            'maximum_lateness_seconds':maximum,'limit_ms':maximum_ms,
            'measurement':'publisher call start versus scheduled source time'}
