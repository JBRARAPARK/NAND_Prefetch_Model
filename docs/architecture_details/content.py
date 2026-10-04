"""Korean design narrative; shared by PDF, Word, and content.json."""


def build_sections(d):
    def p(text):return {'type':'paragraph','text':text}
    def h(text):return {'type':'heading','text':text}
    def b(*items):return {'type':'bullets','items':list(items)}
    def f(text):return {'type':'formula','text':text}
    def fig(name,caption):return {'type':'figure','name':name,'caption':caption}
    def t(headers,rows,widths=None):return {'type':'table','headers':headers,'rows':rows,'widths':widths}
    def page(title,lead,*blocks):return {'title':title,'lead':lead,'blocks':list(blocks)}
    def val(r,key):return f'{float(r[key]):.2f}'
    pages=[]
    pages.append(page('전체 구조와 설계 결론','4포트 NAND 프리페치 모델 상세 설명자료 | 2026년 10월 4일',
        p('목적은 프리페치와 조회 병렬성이 Host 성능·미완료 요청 수·에너지에 어떤 영향을 주는지 설명하는 것이다. 현재 구현, 실행으로 확인한 수치, 구현 시 확인할 가정을 연결했다. 최대 처리량 256GB/s와 그 25%인 64GB/s를 각각 다룬다.'),
        t(['항목','현재 구성과 판단'],[
            ['Host 연결','512bit·1GHz 독립 포트 4개, 64B burst. 포트당 64GB/s, 합계 256GB/s 이론 상한.'],
            ['기본 조회','500MHz·500ns, 포트당 파이프라인 2개·조회 슬롯 500개. Ready 최대 성능에는 outstanding 502개/포트.'],
            ['NAND 공급','128개 독립 채널·채널당 2.4GB/s, global_striped 배치. 포트당 outstanding 10,000개에서 후반 256GB/s 확인.'],
            ['64GB/s 유지','프리페치 데이터 준비 시 outstanding 128개/포트 권장. 프리페치 없음은 2,560개/포트 권장.'],
            ['추가 판단 지연','미리 판단하면 선행 시간에 반영. AR 이후 100·200·300ns 판단은 160·192·224개/포트 권장.'],
            ['파워 판단','평균 파워와 같은 작업량의 에너지를 함께 비교. EU 예시 계수이며 실측 W·J와 구분.']], [22,78]),
        h('자료 구성'),
        p('2–4쪽: 전체 구조·요청 단위·실행 흐름 / 5–7쪽: 프리페치·판단·조회 병렬성 / 8–10쪽: NAND·주소 배치·버퍼와 순서 / 11–13쪽: 최대 성능·64GB/s·판단 지연 / 14–15쪽: 파워 모델과 결과 / 16–20쪽: 구현·검증·확장 항목·전체 파라미터.'),
        p('읽는 기준: 모든 outstanding·lookup 슬롯·파이프라인 수는 별도 표시가 없으면 포트당이다. 처리량은 4포트 합계다. GB/s는 십진 단위, KiB·MiB는 이진 단위다. 시간 설정은 µs이며 100ns는 0.1µs다.')))

    pages.append(page('시스템 블록 구조','포트별 제어 자원은 독립이고 NAND page와 controller buffer는 공유한다.',
        fig('architecture','현재 시뮬레이터의 논리 연결. 공유 page 상태가 hit 판정·읽기 병합·반환 가능 여부를 연결한다.'),
        t(['영역','역할','공유 범위'],[
            ['Host 포트','AR 수락, outstanding 관리, Host 판단, 조회 FIFO, R FIFO·전송','포트별 독립'],
            ['조회 상태','burst 조회 완료 여부, page ready 상태, 대기 burst 집합','조회 실행은 포트별, page 상태는 공유'],
            ['프리페치','예측 시점 → 판단 완료 → page 요청 생성','요청 단위의 선행 경로'],
            ['NAND','command·sense·channel 전송·ECC, 같은 page의 읽기 병합','모든 포트가 공유'],
            ['Controller buffer','page당 credit 선점, ready 데이터 유지, 전체 반환 후 해제','8MiB 공유 용량']], [21,55,24]),
        p('도식은 논리 구조다. 실제 내부 crossbar·SRAM bank·PHY·CDC 회로의 중재와 지연은 독립 블록으로 구현되지 않았다. 256GB/s의 내부 데이터 경로가 확보된다는 가정 아래 외부 포트·조회·NAND 병목을 비교한다.')))

    pages.append(page('요청·page·burst·포트의 관계','Outstanding 한 개는 64KiB 논리 요청 한 개가 아니라 64B burst 한 개다.',
        f('64KiB 요청 = 4 × 16KiB page = 1,024 × 64B burst'),
        f('16KiB page = 256 bursts = 포트별 64 bursts'),
        t(['단위','분할과 식별','완료 조건'],[
            ['논리 요청','request ID, 64KiB, page 4개','구성 burst 중 가장 늦은 RLAST'],
            ['NAND page','page_id = burst_id // 256','16KiB NAND 읽기는 여러 burst가 공유'],
            ['AXI burst','64B = 512bit 한 beat','AR 수락부터 해당 RLAST까지 outstanding 점유'],
            ['Host port','port = burst_id % 4','각 포트의 수락 순서대로 R 반환']], [23,45,32]),
        h('첫 요청의 분배 예'),
        t(['포트','배정 burst ID','포트별 요청 데이터'],[
            ['0','0, 4, 8, …, 1,020','256 × 64B = 16KiB'],
            ['1','1, 5, 9, …, 1,021','16KiB'],
            ['2','2, 6, 10, …, 1,022','16KiB'],
            ['3','3, 7, 11, …, 1,023','16KiB']], [18,50,32]),
        b('하나의 page를 네 포트가 동시에 참조해도 NAND 읽기는 한 번만 실행한다.',
          '64GB/s에서 64KiB 요청의 입력 간격은 1.024µs다. 256GB/s에서는 이상적으로 0.256µs다.',
          '4포트에 균등 분배한 현재 workload의 수치다. 실제 주소·요청의 포트 편중은 별도 검증이 필요하다.'),
        p('용어: AR은 읽기 주소 수락, R은 읽기 데이터 반환, RLAST는 burst 마지막 데이터 완료다. II는 initiation interval, 즉 같은 lane이 새 조회를 시작할 수 있는 간격이다. ECC는 오류 정정 단계이고 QD는 동시에 진행하는 논리 요청 수다.')))

    pages.append(page('Demand hit·late·miss 실행 흐름','조회 완료와 page 준비가 모두 충족돼야 반환할 수 있다.',
        fig('demand_flow','AR 수락 이후 판단·조회·page 상태 확인·포트 내부 FIFO·R 반환으로 이어지는 경로.'),
        t(['경로','page 상태','처리'],[
            ['Ready prefetch hit','프리페치 page가 이미 ready','조회 완료 후 FIFO 선두 burst부터 R 시작'],
            ['Late prefetch hit','프리페치 읽기가 진행 중','같은 page 읽기를 병합하고 ready event를 기다림'],
            ['Demand miss','page 요청이 아직 없음','조회 완료 시 page 생성 → NAND dispatch → ready'],
            ['순서 대기','자기 데이터는 준비됐지만 선두가 미준비','같은 포트에서 R 대기; 다른 포트는 독립 진행']], [26,34,40]),
        p('hit_at_ar와 hit_at_lookup은 서로 다른 시점의 표본이다. 조회 중 page가 준비되면 AR 시점 late가 조회 완료 시 ready로 바뀔 수 있다. 현재 snapshot은 프리페치로 생성된 page만 hit로 분류한다. Demand로 생성된 page가 나중에 ready여도 프리페치 hit 비율에는 포함하지 않는다.'),
        p('반환 가능 조건 eligible은 lookup_done과 page.ready다. 각 포트의 returns 선두만 반환하며 R은 한 포트에서 한 번에 하나의 burst를 전송한다. Lookup은 병렬로 진행하고 page 준비 event가 관련 burst를 깨운다.'),
        p('입력 demand event에서 burst가 AR 대기열에 들어간다. 대기열은 무제한이다. AR 이전 입력 대기는 outstanding에 포함되지 않지만 demand 기준 요청 완료 지연에는 포함된다.')))

    pages.append(page('프리페치 선행 경로와 예측 시나리오','판단 지연은 프리페치를 시작할 수 있는 시간을 늦춘다.',
        fig('timing','모델에서 추출한 첫 burst의 상대 타이밍. AR=0ns, R은 1ns이며 끝점을 표시했다. 선행 판단의 잔여 대기와 Host 판단의 직접 지연을 구분한다.'),
        f('예측 시점 = demand 시점 - lead'),
        f('speculative page 요청 시점 = 예측 시점 + prefetch_decision_us'),
        t(['시나리오','동작','용도'],[
            ['none','선행 prefetch event 없음','Demand가 NAND 읽기를 시작하는 기준'],
            ['ready','모든 요청에 early_lead_us 선행 event','충분한 lead에서는 ready hit 상한; 짧은 lead면 late 가능'],
            ['late','모든 요청에 late_lead_us 선행 event','읽기가 진행 중인 prefetch의 효과'],
            ['mixed','홀수 요청에 early prefetch, 짝수는 none','선행 여부 혼합과 순서 대기 확인']], [18,49,33]),
        h('Lead와 준비 조건'),
        p('현재 NAND에서 경합 없는 page 준비는 약 9.256667µs다. AR 이전 ready를 보장하려면 lead가 이 시간 + 판단 지연보다 커야 한다. 100·200·300ns 판단에는 각각 약 9.357·9.457·9.557µs가 필요하다. 최신 실험은 lead 10µs를 사용해 세 조건 모두 AR ready hit 100%를 확인했다.'),
        f('추가 NAND 대기 근사 = max(0, NAND 시간 - (lead - 판단 지연) - 조회 시간)'),
        p('위 식은 경합 없는 선행 page의 잔여 대기 설명이다. 실제 burst 지연에는 AR 대기·lookup queue·clock edge·포트 FIFO가 추가된다. 조회 500ns와 NAND 준비가 겹치므로 판단 지연을 모든 burst에 무조건 더하면 선행 경로의 효과를 과소평가한다.'),
        p('4포트 모델은 정해진 요청의 page를 미리 만드는 시나리오 모델이다. 예측 후보 생성·confidence·학습·오예측률은 구현하지 않았다. sim.py의 후보 정확도·adaptive 정책은 별도 baseline 기능이며 현재 4포트 경로에 자동으로 연결되지 않는다.')))

    pages.append(page('판단 단계를 어디에 배치하는가','같은 판단 지연을 선행 경로와 Host 경로에 두 번 넣지 않는다.',
        t(['비교','선행 판단','Host 이후 판단'],[
            ['설정','prefetch_decision_us','host_decision_us'],
            ['판단 단위','64KiB 예측 요청','수락된 64B burst'],
            ['진입 시점','demand - lead','Host AR 수락'],
            ['점유 자원','별도 판단 자원은 현재 무제한 가정','Host outstanding 점유, lookup 슬롯은 아직 미점유'],
            ['성능 영향','선행 시간 감소, page 준비 시점 변화','AR→RLAST 지연에 직접 추가'],
            ['프리페치 없음','event가 없으므로 영향 없음','공통 Host 회로로 설정하면 none에도 적용']], [23,38,39]),
        h('Host 이후 판단의 병렬성 조건'),
        f('64GB/s 목표: 포트당 새 64B 판단 투입 간격 ≤ 4ns'),
        t(['판단 지연','필요한 판단 중 동시 건수 / 포트','조회 슬롯과의 관계'],[
            ['100ns','ceil(100 / 4) = 25','판단 중에는 lookup 슬롯 미점유'],
            ['200ns','50','판단과 조회는 별도 단계'],
            ['300ns','75','두 단계 모두 충분한 투입률 필요']], [22,43,35]),
        p('현재 host_decision은 각 burst를 지정된 시간 후 lookup queue로 이동시키는 완전 파이프라인 가정이다. 판단 슬롯 수나 initiation interval 제한은 구현하지 않았다. 256GB/s 목표에서는 포트당 투입 간격이 1ns 이하이고 동시 판단 건수는 100·200·300개 이상으로 늘어난다.'),
        p('판단이 100ns마다 하나씩만 처리되는 직렬 burst 회로라면 포트당 상한은 0.64GB/s다. Outstanding만 늘려서는 목표에 도달할 수 없다. 같은 지연이어도 파이프라인 투입률을 반드시 구분해야 한다.')))

    pages.append(page('조회 엔진: 지연·슬롯·파이프라인·outstanding','지연을 숨기는 용량과 새 작업을 시작하는 속도를 따로 관리한다.',
        t(['자원/설정','정의','500MHz 기본값'],[
            ['lookup_us','조회 시작부터 완료까지 서비스 시간','0.5µs = 500ns'],
            ['lookup_slots','동시에 조회 중인 burst 최대 수','500개/포트'],
            ['lookup_pipelines','독립적인 새 조회 투입 lane 수','2개/포트'],
            ['lookup_ii_cycles','lane마다 새 조회를 시작하는 간격','1 cycle = 2ns'],
            ['outstanding','AR부터 RLAST까지 수락된 미완료 burst 최대 수','502개/포트'],
            ['clock edge','Host AR과 조회 clock의 정렬 대기','Ready 기준 최대 1ns 추가']], [26,48,26]),
        f('조회 투입률 = min(P × f / II, C / L)   [burst/s]'),
        f('포트 처리량 상한 ≈ min(Host BW, 조회 투입률 × 64B, O / 응답시간 × 64B)'),
        p('P=2, f=500MHz, II=1이면 투입률은 1G burst/s/포트다. C=500, L=500ns도 1G burst/s다. 두 제한이 모두 포트당 64GB/s와 맞는다. P=1이면 슬롯이 충분해도 포트당 32GB/s, 4포트 합계 128GB/s로 제한된다.'),
        p('Lookup 슬롯은 완료 시 해제된다. Outstanding은 RLAST에서 해제되므로 NAND 대기·순서 대기·R 전송까지 포함한다. NAND가 느리면 lookup_active는 작아도 outstanding이 가득 찰 수 있다.'),
        p('64GB/s 목표는 포트당 250M burst/s이므로 조회 중 최소 슬롯 근사는 125개다. 최신 실험에서는 다른 요인과 분리하기 위해 lookup_slots=500을 유지하고 outstanding만 변경했다. 슬롯 125개로 축소한 설계의 에너지·타이밍은 이 실험으로 검증되지 않았다.')))

    pages.append(page('NAND 공유 스케줄러와 page 상태','Plane의 읽기 동작은 병렬이고 channel의 데이터 전송은 직렬이다.',
        fig('nand_states','queued → command → sense → sensed → transfer → ECC → ready → returned 상태와 자원 해제 시점.'),
        t(['단계','시간 / 16KiB page','자원 처리'],[
            ['Command','0.1µs','chip별 command 직렬; buffer·plane 선점'],
            ['Sense tR','2.08µs','command 자원 해제, 해당 plane 읽기 계속'],
            ['Channel transfer','16,384 / 2,400 = 6.826667µs','channel당 하나의 전송만 실행'],
            ['Turnaround','0.05µs','channel 점유 시간에 포함'],
            ['ECC','0.2µs','전송 완료에서 channel·plane 해제, ECC 이후 ready'],
            ['Page ready','합계 약 9.256667µs','관련 burst를 깨우고 전체 반환까지 buffer 유지']], [24,34,42]),
        p('Lookup 이후 demand miss라면 조회 0.5µs를 앞에 더해 page 준비까지 약 9.756667µs가 된다. 이 값은 경합 없는 최초 준비 시간이며 데이터 전송은 page 전체가 ECC를 마친 뒤 시작한다. NAND 내부 sub-page streaming은 구현하지 않았다.'),
        p('각 chip에 plane 6개가 있고 command는 chip 단위로 직렬화된다. Plane는 전송 완료까지 점유되지만 서로 다른 plane는 command 이후 sense를 겹칠 수 있다. 같은 channel에 연결된 plane들이 대역폭을 각각 2.4GB/s씩 받는 것은 아니다.'),
        p('128chip·128channel·768plane는 스케줄러의 추상 자원이다. Package·die·LUN의 실제 대응, multi-plane same-row 제약, 실제 NAND 제품의 tR 분포는 이 구성만으로 확정하지 않는다.')))

    pages.append(page('주소 배치·채널 확장·내부 연결','채널 수를 늘려도 주소가 분산되지 않으면 자원을 사용하지 못한다.',
        f('global_striped: chip = page_id % chips'),
        f('plane = (page_id // chips) % planes; channel = chip % channels'),
        t(['요청/page 예','chip','plane','channel'],[
            ['page 0…3 / 첫 요청','0…3','0','0…3'],
            ['page 124…127 / 32번째 요청','124…127','0','124…127'],
            ['page 128…131 / 다음 요청','0…3','1','0…3']], [46,18,18,18]),
        p('기존 striped는 요청 시작 chip과 요청 내부 page로 배정한다. 확장 조건의 유한 동시 요청 창에서는 활성 chip이 일부에 집중될 수 있다. global_striped는 전체 page ID를 이용해 선행 요청 창 안의 연속 page를 모든 채널로 퍼뜨린다.'),
        f('Host 최대: 4 × 512bit × 1GHz / 8 = 256GB/s'),
        f('NAND 원시 상한: 128 × 2.4GB/s = 307.2GB/s'),
        p('원시 대역폭만 보면 ceil(256/2.4)=107채널이다. 그러나 16KiB마다 turnaround 50ns를 포함하면 채널당 약 2.38255GB/s이므로 대역폭만의 경계도 108채널로 늘어난다. Command·plane·버퍼·주소 경합과 여유를 고려한 실험 구성은 128채널이다.'),
        p('내부 연결은 네 R 포트에 합계 256GB/s를 공급해야 한다. SRAM 읽기 bank·crossbar·ECC 출력 경로가 그 속도를 처리해야 하고 NAND 데이터를 받아 적는 write traffic도 고려해야 한다. 단일 포트·단일 bank의 256GB/s 읽기 가정만으로 동시 write 요구까지 검증된 것은 아니다.')))

    pages.append(page('Controller buffer·순서 보장·진행 보호','용량은 읽기 중인 예약 공간과 준비된 데이터 모두에 사용된다.',
        t(['상태','Buffer credit','해제/진행 규칙'],[
            ['NAND issue 전','page당 16KiB 선점','공간 부족이면 queued에 유지'],
            ['Sense·transfer·ECC','예약 공간 유지','동일 page의 여러 포트 참조는 공간 중복 없음'],
            ['Ready·일부 반환','resident data와 credit 유지','page의 256개 burst 반환 완료까지 유지'],
            ['Page 전체 반환','16KiB 해제','다음 queued 읽기 진행 가능'],
            ['선두 page 공간 부족','가장 오래된 미반환 page의 공간 보호','나중 page가 공간을 모두 차지하는 deadlock 방지']], [25,33,42]),
        h('포트 안과 포트 사이의 순서'),
        p('포트 내부는 AR 수락 순서대로 반환한다. 뒤 burst가 ready여도 선두 burst가 미준비면 HOL(head-of-line) 대기가 생긴다. 포트 간 전역 반환 순서는 없으므로 포트 0이 기다려도 포트 1–3은 반환할 수 있다. 하나의 논리 요청 완료 시점만 구성 burst의 최대 RLAST로 묶는다.'),
        h('관측된 버퍼 사용'),
        p('8MiB ready 포화 실험은 전체 데이터를 미리 넣으므로 peak가 8MiB다. 128채널 NAND 최대 성능 실험의 peak는 약 2.28MiB였다. 64GB/s·lead 10µs streaming 실험의 peak는 720,896B, 약 0.6875MiB였다. 이는 해당 workload의 관측값이며 최소 안전 버퍼 크기는 아니다.'),
        p('Ready 데이터의 TTL·eviction·재사용 cache·다중 후보 오예측으로 인한 buffer 경쟁은 4포트 모델에 없다. 실제 SRAM 용량 결정에는 주소 편중, 긴 tR·retry, speculative 낭비, write/read bank 충돌을 추가해야 한다.')))

    performance=[]
    for case,design,label in [('ready_O502','fast','Ready · 1GHz/0ns'),('ready_O502','slow','Ready · 500MHz/500ns'),
                              ('nand_4ch','slow','NAND · 4채널'),('nand_32ch','slow','NAND · 32채널'),
                              ('nand_64ch','slow','NAND · 64채널'),('nand_128ch','slow','NAND · 128채널'),
                              ('nand_long','slow','NAND · 128채널·32MiB')]:
        r=d.multi(case,design)
        performance.append([label,f'{int(r["requests"])/16:g}',val(r,'throughput_gbps'),val(r,'tail_throughput_gbps')])
    pages.append(page('256GB/s 성능의 검증 결과','Host 상한·NAND 공급 능력·초기 지연을 구분해서 읽는다.',
        t(['실행 조건','MiB','전체 평균 GB/s','후반 GB/s'],performance,[43,13,22,22]),
        fig('bandwidth','500MHz·500ns NAND 공급 실험. Outstanding은 포트당 10,000개이며 채널 수 외 조건은 해당 CSV를 따른다.'),
        p('Ready 502개/포트의 후반 256GB/s는 Host·조회 경로의 상한 검증이다. 128채널 NAND는 후반에 같은 상한에 도달하지만 8MiB 전체 평균은 초기 대기로 197.26GB/s다. 전송량을 32MiB로 늘리면 전체 평균이 238.26GB/s로 올라간다.'),
        p('Outstanding 502개/포트인 cold NAND는 전체 평균 13.41GB/s다. 기존 striped 배치의 cold 128채널은 64.31GB/s다. 채널 수 확대만으로는 충분하지 않으며 넓은 요청 창과 실제 page 분산이 함께 필요하다.')))

    ready=d.decision('host_ready_0ns_O128');cold=d.decision('cold_host_0ns')
    pages.append(page('64GB/s 유지에 필요한 outstanding','25%를 넘지 않는 값과 25% 이상을 유지하는 값은 다르다.',
        f('O 근사 = ceil(포트당 목표 BW × AR→RLAST 시간 / burst bytes)'),
        f('16GB/s / 64B = 250M burst/s = 250 burst/µs'),
        t(['조건','지연 근사','필요량 근사 / 포트','권장 / 포트','4포트 합계'],[
            ['Ready prefetch','약 0.502µs','126','128','512'],
            ['프리페치 없음','약 9.758µs','약 2,440','2,560','10,240']], [25,21,22,16,16]),
        t(['검증 조건','전체 평균 GB/s','후반 GB/s','근거'],[
            ['Ready · 128개/포트',val(ready,'full_gbps'),val(ready,'tail_gbps'),'8MiB 포화 입력'],
            ['Cold · 2,560개/포트',val(cold,'full_gbps'),val(cold,'tail_gbps'),'32MiB 포화 입력']], [36,19,19,26]),
        p('앞서 25% 이하 근사값으로 제시한 ready 125개/포트는 후반 63.77GB/s로 목표에 조금 못 미친다. 64GB/s 이상 유지 기준에서는 126개가 관측 경계이고 128개를 권장한다. Cold 필요량은 page 병합·전송 배치 때문에 단순 지연식과 유한 관측 결과가 조금 다를 수 있다.'),
        p('권장값 기준 Host가 동시에 참조하는 burst bytes는 ready 4×128×64B=32KiB, cold 4×2,560×64B=640KiB다. 이는 outstanding 창의 데이터 양이며 buffer의 실제 최소 크기나 speculative 공간과 같지 않다.'),
        p('프리페치는 NAND 읽기를 없애기보다 Host 수락 이전으로 옮긴다. Host outstanding 요구량은 줄지만 NAND 선행 요청·버퍼·예측 상태 자원은 여전히 필요하다.'),
        p('Outstanding만으로 정확히 64GB/s에 제한하려 하면 hit/miss와 지연에 따라 처리량이 바뀐다. 엄격한 상한이 목적이면 포트당 64B AR을 4ns마다 수락하는 rate control이 필요하다. 이 rate limiter는 아직 구현되지 않았다.')))

    decision_table=[]
    for ns,o,bound in [(0,128,126),(100,160,152),(200,192,176),(300,224,202)]:
        r=d.decision(f'host_ready_{ns}ns_O{o}')
        decision_table.append([str(ns),str(bound),str(o),str(4*o),val(r,'tail_gbps')])
    pages.append(page('100·200·300ns 판단 지연 반영 결과','선행 경로와 AR 이후 경로를 별도 설정으로 확인했다.',
        fig('decision_outstanding','같은 64GB/s 목표라도 판단 위치에 따라 필요한 Host 요청 창이 달라진다.'),
        t(['Host 판단 ns','관측 경계 / 포트','권장 / 포트','권장 합계','권장 후반 GB/s'],decision_table,[20,21,18,18,23]),
        p('위 표는 ready 데이터와 별개로 AR 이후 판단이 기존 조회 500ns에 추가되는 구성이다. 판단 100ns당 약 25개/포트가 더 필요하다. 8MiB의 유한 관측 구간에서는 151개·201개가 후반 64GB/s에 조금 못 미쳐 152개·202개를 추가 검증했다. 176개는 후반 64GB/s 이상이지만 초기 대기를 포함한 전체 평균은 63.89GB/s다.'),
        p('선행 판단 100·200·300ns는 lead 10µs에서 모두 AR ready hit 100%, outstanding 128개/포트로 후반 64GB/s를 유지했다. 전체 평균은 초기 조회 대기를 포함해 63.9869GB/s였다. 같은 판단을 두 설정에 중복 반영하지 않는다.'),
        p('프리페치 없음에 AR 이후 공통 판단 회로를 남긴 추가 비교에서는 2,560개/포트에서 300ns까지 전체·후반 모두 64GB/s 이상이었다. 300ns 후반 값은 64.41GB/s로 여유가 작다. 판단을 비활성화하면 기본 cold 조건의 66.40GB/s로 돌아간다.')))

    pages.append(page('파워 모델: 평균 파워와 총 에너지','작업이 오래 걸리면 평균 파워가 낮아져도 같은 작업의 에너지가 늘 수 있다.',
        f('E_total = E_clock + E_lookup + E_queue + E_leakage + E_background + E_AXI + E_NAND'),
        f('평균 파워 = E_total / 관측 시간;  데이터당 에너지 = E_total / 반환 bytes'),
        t(['에너지 항','현재 계산 방식','범위'],[
            ['Clock','활성 clock edge 수 × (1 + 0.002×슬롯 + 0.05×lane) × 전압비²','포트별 engine, EU/cycle'],
            ['Lookup operation','총 burst 수 × 8 × 전압비²','조회 1회 비용, EU/operation'],
            ['Queue transition','burst별 enqueue+dequeue × 0.5 × 전압비²','FIFO 활동'],
            ['Leakage','시간 × 포트 수 × (100 + 0.1×슬롯 + 1×lane)','전압비로 자동 축소하지 않음'],
            ['Background','관측 시간 × 200','고정 공유 배경 항'],
            ['AXI/NAND bytes','반환 bytes×0.05 / 관측 창 NAND bytes×0.5','NAND 같은 page 중복 과금 없음']], [24,52,24]),
        p('EU는 예시 상대 에너지 단위다. EU/µs를 실제 W로 바꾸려면 소자·전압·클럭·메모리·PHY별 에너지 계수가 필요하다. lookup_voltage_v는 clock·operation·queue switching 항에만 제곱으로 적용된다. Leakage·AXI·NAND를 함께 낮추는 가정은 하지 않는다.'),
        p('Clock gating은 포트별 engine 전체에 적용한다. AR 이후 대기부터 lookup 완료와 lane II 종료까지 활성 구간을 합치고 clock edge를 센다. Always-on은 관측 창 전체를 센다. 개별 슬롯별 fine-grained gating은 아니다.'),
        p('관측 창은 첫 AR부터 마지막 RLAST까지다. Ready 실험의 사전 프리페치 시간·에너지는 제외된다. NAND 전송 완료가 창 안에 있는 page만 NAND energy에 포함된다. 따라서 ready/cold의 전체 업무 에너지를 비교하려면 warmup 비용을 추가해야 한다.')))

    power=[]
    for case,label in [('ready_O502','Ready · 8MiB'),('nand_long','NAND · 32MiB')]:
        fast=d.multi(case,'fast')
        for variant,vlabel in [('same_voltage_gated','500MHz · 1V'),('lower_voltage_gated','500MHz · 0.8V')]:
            slow=d.multi(case,'slow',variant)
            power.append([label,vlabel,f'{100*float(slow["mean_total_power_eu_per_us"])/float(fast["mean_total_power_eu_per_us"]):.1f}%',
                          f'{100*float(slow["total_energy_eu"])/float(fast["total_energy_eu"]):.1f}%'])
    pages.append(page('파워 결과와 설계 선택','비교 기준은 같은 작업·gating·1GHz 1V 설계이며 fast 슬롯은 slow의 4배다.',
        t(['작업','비교 설계','평균 파워비','총 에너지비'],power,[25,29,23,23]),
        fig('energy','1GHz·0ns·슬롯 2,000개/포트 기준의 총 에너지 비율. Slow는 슬롯 500개/포트, lane 수는 양쪽 2개다.'),
        p('Ready에서 같은 전압의 slow 에너지는 기준의 76.3%, 0.8V 가정은 55.8%다. Cold NAND 32MiB에서는 NAND·AXI 같은 고정 도메인의 비중 때문에 91.5%·84.2%로 절감 폭이 작아진다. 평균 파워비와 에너지비는 실행시간 차이 때문에 일치하지 않는다.'),
        p('Fast 슬롯 4배는 더 넓은 동시 조회 용량을 제공하지만 이 모델의 슬롯 clock·leakage 비용도 늘린다. 이 결과를 주파수만 반으로 줄인 효과라고 해석하면 안 된다. 같은 슬롯 비교와 4배 슬롯 비교를 구분해야 한다.'),
        p('현재 가정에서 성능을 유지하는 slow·gating·저전압 구성이 에너지에 유리하다. 실제 선택에는 0.8V에서 500MHz timing closure, SRAM·CDC·PHY 전력, NAND 128채널의 정적 전력, 사전 프리페치와 오예측 비용을 포함해야 한다. 판단 회로 자체의 추가 에너지는 아직 계수화하지 않았다.')))

    pages.append(page('소스 구조와 모델의 역할 분담','서로 다른 모델의 기능이 자동으로 합쳐진 것은 아니다.',
        t(['파일/계층','구현 역할','적용 범위'],[
            ['sim.py','요청·page 단위 baseline: target known·mapping delay, fixed/adaptive, 오예측, retry, bank, QD, NPU 완료','기존 TLC 민감도 모델'],
            ['axi_burst_sim.py','burst admission, lookup slot·clock·lane, page 병합, buffer, 단일 R 순서','단일 포트 timing baseline'],
            ['multiport_sim.py','독립 포트 AR/R·FIFO·조회, 공유 NAND, 판단 두 경로, 공통 tail 측정','현재 4포트·256/64GB/s 분석'],
            ['lookup_power.py','clock·조회·queue·leakage·배경·AXI·NAND EU 계산','표본 기반 상대 에너지'],
            ['experiments/','조건 생성·CSV·config·hash manifest','실행·결과 재현'],
            ['docs/execution_model/','과거 단일 포트 결과의 GUI','최신 4포트 자료와 구분']], [26,51,23]),
        h('핵심 함수 연결'),
        b('MultiportSimulator.run: demand·AR·판단·lookup·NAND·RLAST event 처리.',
          'schedule_host_ar: 포트별 outstanding과 AR clock 간격을 확인해 admission 예약.',
          'start_port_lookups: FIFO, 슬롯 cap, lane II, lookup clock edge를 적용.',
          'Simulator.dispatch: page ID 순으로 buffer·plane·command·channel 자원 검사.',
          'start_r / eligible: 포트 FIFO 선두의 조회 완료·page ready 조건 검사.',
          'head_page: 모든 포트 중 가장 오래된 미반환 page의 공간 보호.',
          'measure_energy: 완료된 실행의 burst/page 기록으로 관측 창 에너지 집계.'),
        p('4포트 모델은 Config와 NAND 공통 동작을 단일 포트 모델에서 상속한다. sim.py의 adaptive·오예측·retry·bank 옵션은 별도 모델에만 있다. 코드에서 존재하는 것과 이번 결과에 실제 적용한 것을 구분해 확장해야 한다.')))

    pages.append(page('검증·측정 정의·재현 방법','실험 결과의 조건과 관측 창을 함께 보관한다.',
        t(['항목','정의/검증'],[
            ['전체 처리량','전체 bytes / (마지막 RLAST - 첫 AR). 초기 조회·NAND 대기 포함.'],
            ['후반 처리량','완료 burst 절반 시점 뒤의 bytes / 공통 종료 시간차. 동일 tick 완료도 일관 처리.'],
            ['요청 완료 지연','max constituent RLAST - demand. AR 이전 대기 포함.'],
            ['요청 서비스 시간','max constituent RLAST - 첫 AR. 입력 admission 대기와 구분.'],
            ['HOL idle','포트 선두가 미준비이지만 뒤에 준비 burst가 있는 R idle.'],
            ['50개 테스트','기존 43개 + 판단 위치·겹침·demand 우선·점유·정수 ns recurrence·비활성·입력 검증 7개.']], [27,73]),
        p('후반 처리량은 유한 실행 구간의 평균이며 무한 시간의 정상 상태를 보장하지 않는다. 포트별 서로 다른 tail 창을 더한 sum_port_tail_throughput_gbps는 합계 비교의 대표값으로 사용하지 않는다. 공통 tail_throughput_gbps를 사용한다.'),
        h('재현 명령'),
        f('python3 -m unittest -q\npython3 experiments/run_prefetch_decision.py\npython3 experiments/run_multiport_256.py\npython3 experiments/summarize_multiport_256.py'),
        p('세부 manual 실행은 multiport_sim.py --config <JSON> --out <경로>를 사용한다. --trace로 event CSV를 기록한다. 대규모 sweep은 record_trace=false로 메모리 사용을 줄인다. 최신 4포트 sweep 24실행·60에너지 행, 판단 지연 sweep 26실행을 근거로 사용했다.'),
        p('이 자료의 evidence.json에는 선택한 원본 행, 입력 CSV와 소스의 SHA-256, 모델 commit, 문서 구성·출력 hash를 저장한다. 과거 실험 manifest는 실행 당시 소스 snapshot이고 판단 지연 추가 이후의 현재 소스 hash와 다를 수 있다. 기존 기록을 소급 수정하지 않는다.')))

    pages.append(page('적용 범위와 다음 모델 개선','성능 유지 조건을 실제 구현에서 확인할 항목으로 연결한다.',
        t(['확인할 설계 요소','현재 처리','다음 검증'],[
            ['Host/내부 데이터 경로','독립 AR/R, 이상적 512bit 1GHz','READY·ID·PHY·protocol·CDC·SRAM bank·fabric arbitration'],
            ['판단 엔진','고정 지연·완전 파이프라인','판단 슬롯·II·단위·clock·실제 에너지'],
            ['예측 품질','정해진 요청의 선행 event','trace 기반 후보·confidence·오예측·취소·낭비'],
            ['NAND media','고정 tR·chip/plane/channel','die/LUN·same-row·retry·tR 분포·P/E/GC 경합'],
            ['Buffer/cache','유한 page credit, 순서 보호','TTL·eviction·재사용·multi-candidate 경쟁'],
            ['전력','예시 EU 계수, 고정 공유 배경','추가 NAND 채널·PHY·SRAM·fabric·warmup 실측 계수'],
            ['64GB/s 상한','O로 처리 용량 확보','AR 4ns admission rate limiter와 workload 변동 검증']], [26,32,42]),
        h('구현 판단 순서'),
        b('먼저 목표가 최대 용량인지, 최소 지속 성능인지, 엄격한 상한인지 정의한다.',
          '판단을 Host 이전에 숨길 수 있는 lead와 예측 정확도를 확인한다.',
          'Host·판단·조회·NAND·내부 연결 중 가장 작은 처리 용량을 찾는다.',
          '측정 지연으로 outstanding·lookup 슬롯·판단 동시 건수를 산정한다.',
          '긴 전송과 실제 주소 trace로 평균·p95·HOL·버퍼를 확인한다.',
          '동일 작업량 에너지와 성능을 함께 비교해 전압·슬롯·gating을 결정한다.'),
        p('Host AR은 최소 1ns 간격을 적용하며 NAND 완료 등으로 재개될 때 실제 Host clock edge로 다시 정렬하는 RTL 동작은 모델링하지 않는다. Ready 조건의 1ns lookup 정렬 대기를 일반적인 CDC 지연 상한으로 해석하지 않는다.'),
        p('현재 자료는 모델 구현과 가정 기반 실행의 설명이다. 제품 수치를 확정하려면 위 항목을 실제 설정·측정값으로 보정해야 한다. 임원용 기존 1쪽 보고서는 256GB/s 기본 구성의 요약이고, 이 상세 자료는 최신 판단 지연과 64GB/s 권장값까지 확장한 설명이다.')))

    host_keys=['host_ports','axi_width_bits','axi_clock_mhz','burst_bytes','request_bytes','requests',
               'outstanding','lookup_clock_mhz','lookup_us','lookup_slots','lookup_pipelines',
               'lookup_ii_cycles','prefetch_decision_us','host_decision_us']
    notes={
        'host_ports':'독립 AR/R 포트 수','axi_width_bits':'bit / 포트','axi_clock_mhz':'MHz, AR 1cycle·R 데이터 폭',
        'burst_bytes':'B, 현재 512bit 한 beat','request_bytes':'B, 논리 요청 크기','requests':'논리 요청 개수',
        'outstanding':'burst 수 / 포트, 기본은 최대 ready 성능용','lookup_clock_mhz':'MHz, None은 clock 제한 생략',
        'lookup_us':'µs, 조회 서비스 시간','lookup_slots':'개 / 포트, None은 무제한',
        'lookup_pipelines':'lane 수 / 포트','lookup_ii_cycles':'cycle / lane의 새 조회 투입',
        'prefetch_decision_us':'µs, 선행 판단 지연','host_decision_us':'µs, AR 이후 판단 지연',
        'page_bytes':'B, NAND page 크기','chips':'추상 chip 수','channels':'독립 NAND 전송 채널 수',
        'planes':'chip당 plane 수','mapping':'page→chip/plane/channel 배치',
        'tr_us':'µs, sense 시간','io_gbps':'GB/s / NAND channel','command_us':'µs, chip별 command 점유',
        'turnaround_us':'µs, channel 전송 점유에 포함','ecc_us':'µs, ECC 완료 후 ready',
        'buffer_bytes':'B, 예약+ready controller buffer',
        'scenario':'none / ready / late / mixed','period_us':'µs, 0은 요청 동시 도착',
        'first_demand_us':'µs, 첫 demand 및 lookup clock 위상 기준','early_lead_us':'µs, ready/mixed 예측 lead',
        'late_lead_us':'µs, late 예측 lead','record_trace':'event trace 저장 여부'}
    def params(keys):
        return [[key,str(d.defaults[key]),notes[key]] for key in keys]
    pages.append(page('전체 파라미터 사전: Host·판단·조회','MultiportConfig의 코드 기본값이며 실험별 override와 구분한다.',
        t(['설정 이름','코드 기본값','의미 / 단위'],params(host_keys),[37,19,44]),
        h('64GB/s 권장 override'),
        p('선행 프리페치: scenario=ready, outstanding=128, early_lead_us=10, prefetch_decision_us=0.1/0.2/0.3, host_decision_us=0. Host 이후 판단: ready 데이터·outstanding=160/192/224, host_decision_us=0.1/0.2/0.3, prefetch_decision_us=0.'),
        p('Cold 64GB/s: scenario=none, outstanding=2560. 기존 lookup_slots=500·lookup_pipelines=2를 유지한다. 모델의 기본 outstanding=502는 256GB/s ready 목적이므로 64GB/s용 기본값으로 해석하지 않는다.'),
        p('Fast 비교 override는 lookup_clock_mhz=1000, lookup_us=0, lookup_slots=2000이다. Host 포트는 양쪽 모두 512bit·1GHz이며 Host clock을 500MHz로 낮춘 비교가 아니다.')))

    rest=[key for key in d.defaults if key not in host_keys]
    pages.append(page('전체 파라미터 사전: NAND·workload','Source commit: '+d.commit[:12],
        t(['설정 이름','코드 기본값','의미 / 단위'],params(rest),[37,19,44]),
        h('근거 파일'),
        b('results/multiport_256/sweep.csv · manifest.json: 256GB/s 확장 및 상대 에너지.',
          'results/prefetch_decision_64/sweep.csv · configs.json · manifest.json: 판단 지연 26조건.',
          'multiport_sim.py · axi_burst_sim.py · lookup_power.py: 현재 구현.',
          'test_multiport.py · test_prefetch_decision.py 및 기존 테스트: 회귀·독립식·자원 보호.',
          'docs/architecture_details/evidence.json: 이 자료의 원본 행·hash·출력 검증.'),
        p('모든 실행 config는 JSON으로 보관된다. µs/ns 변환, GB/s/KiB 구분, 포트당/합계 구분, 포화 입력/64GB/s 입력 구분을 유지해야 수치를 재현할 수 있다.')))
    assert len(pages)==20
    return pages
