import pytest
from haru_recording_bringup.replay_acceptance import arrival_acceptance


def test_complete_delivery_can_still_fail_timing():
    result=arrival_acceptance({'95':{'max':.45,'p99':.40}},100,50)
    assert not result['passed'] and len(result['failures'])==2
    assert result['measurement']=='absolute subscriber arrival error'


def test_limits_are_inclusive_optional_and_require_evidence():
    assert arrival_acceptance({'95':{'max':.1,'p99':.05}},100,50)['passed']
    assert not arrival_acceptance({},100)['passed']
    assert not arrival_acceptance({'95':{'max':None}},100)['passed']
    assert not arrival_acceptance({})['enabled']
    for value in (0,-1,float('nan'),float('inf'),True):
        with pytest.raises(ValueError):arrival_acceptance({},value)


def test_clock_uncertainty_is_included_in_the_budget():
    result=arrival_acceptance({'95':{'max':.055}},100,uncertainty_seconds=.05)
    assert not result['passed'] and result['clock_uncertainty_seconds']==.05


def test_per_domain_limits_do_not_hide_a_slow_domain():
    result=arrival_acceptance({'95':{'max':.01,'p99':.009},'96':{'max':.11,'p99':.09}},100,50)
    assert {f['domain'] for f in result['failures']}=={96}


def test_publisher_schedule_cannot_pass_without_evidence_or_when_overloaded():
    from haru_recording_bringup.replay_acceptance import publisher_acceptance
    assert publisher_acceptance([0,.02],20)['passed']
    assert not publisher_acceptance([0,.020001],20)['passed']
    assert not publisher_acceptance([],20)['passed']
    assert not publisher_acceptance([float('nan')],20)['passed']
    assert publisher_acceptance([],None)['passed']
    for value in (0,-1,float('inf'),True):
        with pytest.raises(ValueError):publisher_acceptance([],value)
