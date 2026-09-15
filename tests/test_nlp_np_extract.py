"""Tests for Nepali event extraction."""

from __future__ import annotations

from landslide_inventory.nlp_np.extract import extract_np

KEYWORDS_CFG = {
    'terms': {'np': ['पहिरो', 'भूस्खलन']},
    'exclude': {'np': ['राजनीतिक पहिरो', 'निर्वाचनमा पहिरो']},
    'trigger_terms': {
        'rainfall': {'np': ['वर्षा', 'अविरल वर्षा', 'भारी वर्षा', 'मनसुन']},
        'earthquake': {'np': ['भूकम्प', 'कम्पन']},
        'road_construction': {'np': ['सडक विस्तार', 'डोजर', 'निर्माण']},
    },
    'casualty_terms': {
        'deaths': {'np': ['मृत्यु', 'मृत', 'ज्यान गुमायो']},
        'missing': {'np': ['बेपत्ता', 'हराइरहेका']},
        'injured': {'np': ['घाइते', 'घाइते भएका']},
    },
}


def test_extract_np_municipality_only_infers_district() -> None:
    result = extract_np(
        None,
        'अविरल वर्षापछि मेलम्ची नगरपालिका क्षेत्रमा पहिरो जाँदा सडक अवरुद्ध भयो।',
        '2024-07-16',
        None,
        KEYWORDS_CFG,
    )
    assert result['municipality'] == 'Melamchi Municipality'
    assert result['district'] == 'Sindhupalchok'
    assert result['place_admin_level'] == 'municipality'
    assert result['class'] == 2


def test_extract_np_ward_case() -> None:
    result = extract_np(
        None,
        'लगातार वर्षापछि मेलम्ची नगरपालिका-११ वडा क्षेत्रमा पहिरो खस्यो।',
        '2024-07-16',
        None,
        KEYWORDS_CFG,
    )
    assert result['ward'] == 'वडा ११'
    assert result['municipality'] == 'Melamchi Municipality'
    assert result['district'] == 'Sindhupalchok'
    assert result['place_admin_level'] == 'ward'


def test_extract_np_bs_to_ad_conversion() -> None:
    result = extract_np(
        None,
        '२०८०-०१-०१ गते मेलम्ची नगरपालिका क्षेत्रमा पहिरो गएको थियो।',
        None,
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2023-04-14'
    assert result['conf_date'] == 0.95


def test_extract_np_metaphor_exclude_case() -> None:
    result = extract_np(
        'निर्वाचनमा पहिरो जित',
        'निर्वाचनमा पहिरो जितको चर्चा चलिरहेको छ।',
        '2024-01-01',
        None,
        KEYWORDS_CFG,
    )
    assert result['class'] == 3



def test_extract_np_infers_previous_day_from_gayerati() -> None:
    result = extract_np(
        'पहिरोले घर पुरिँदा अछाममा एकै परिवारका तीन जनाको मृत्यु',
        'गए राति घरमा सुतिरहेका उनीहरूलाई पहिरोले पुरेको थियो।',
        '2022-07-25',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2022-07-24'


def test_extract_np_promotes_direct_injury_event_to_class_one() -> None:
    result = extract_np(
        'पहिरोले घर भत्किँदा पोखरामा तीन जना घाईते',
        'पोखरा महानगरपालिका क्षेत्रमा पहिरोले घर भत्किँदा ३ जना घाइते भएका छन्।',
        '2017-08-11',
        None,
        KEYWORDS_CFG,
    )
    assert result['class'] == 1
    assert result['injured'] == 3



def test_extract_np_uses_year_hint_for_bs_month_day_without_year() -> None:
    result = extract_np(
        'संखुवासभामा पहिरोमा पुरिएर २ जनाको मृत्यु',
        '१ साउन, सङ्खुवासभा । सिलिचोङ गाउँपालिकामा पहिरोमा पुरिएर दुई जनाको मृत्यु भएको छ।',
        None,
        None,
        KEYWORDS_CFG,
        published_year_hint=2024,
    )
    assert result['event_date_ad'] == '2024-07-16'


def test_extract_np_gayerati_uses_inferred_bs_anchor() -> None:
    result = extract_np(
        'दोलखामा पहिरो : १५ महिने शिशुको मृत्यु, ३ जना बेपत्ता',
        '१९ साउन, काठमाडौं । गएराति ९ बजेतिर पहिरो खस्दा एक शिशुको मृत्यु भएको छ।',
        None,
        None,
        KEYWORDS_CFG,
        published_year_hint=2023,
    )
    assert result['event_date_ad'] == '2023-08-03'


def test_extract_np_followup_title_uses_full_text_anchor_date() -> None:
    result = extract_np(
        'डेढ वर्षअघि ३५ जनाको ज्यान लिएको झ्याप्लेखोला पहिरो नियन्त्रण अन्तिम चरणमा',
        'काठमाडौँ । डेढ वर्षअघि ३५ जनाको ज्यान जाने गरी आएको विनाशकारी झ्याप्ले खोला पहिरो नियन्त्रणको काम ९९ प्रतिशत सम्पन्न भएको छ । २०८१ असोज १२ गते अविरल वर्षासँगै झ्याप्ले खोलामा लेदोसहितको भीषण पहिरो खसेको थियो ।',
        '2026-03-14',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2024-09-28'



def test_extract_np_prefers_same_day_when_today_and_last_night_both_appear() -> None:
    result = extract_np(
        'बांगाबगरमा पहिरो : महाकाली राजमार्ग अवरुद्ध',
        'गएराति परेको पानीले सडकमाथिबाट पहिरो खस्दा महाकाली राजमार्ग अवरुद्ध भएको छ। आज बिहान ७ बजे पहिरो जाँदा यातायात अवरुद्ध बनेको स्थानीयले जानकारी दिए।',
        '2017-08-04',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2017-08-04'



def test_extract_np_supports_month_day_order_without_year() -> None:
    result = extract_np(
        'धुर्मुस–सुन्तली फाउण्डेशनद्वारा पहिरोपीडितलाई राहत वितरण',
        'साउन २८ गते बिहान २ बजे पहिरोमा घरसहित पुरिएर चार जनाको ज्यान गएको थियो।',
        '2017-08-22',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['event_date_ad'] == '2017-08-12'


def test_extract_np_does_not_backshift_gayeratidekhi_rainfall_phrase() -> None:
    result = extract_np(
        'मुग्लिन-नारायणगढ सडक पहिरोले बग्यो, सवारीसाधन अलपत्र',
        'गएरातिदेखि परेको अविरल वर्षाले मुग्लिङ-नारायणगढ सडक खण्ड अवरूद्ध भएको छ।',
        '2017-08-31',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['event_date_ad'] == '2017-08-31'


def test_extract_np_prefers_explicit_bs_date_over_later_weekday_reference() -> None:
    result = extract_np(
        "पहिरोले श्रीमानसहित आठ सदस्य गुमाएकी निशामाईलाई अस्थायी आवासको मल्हमपट्टि",
        "२०७७ साउन ३० गते बिहान ६ः३० बजे खसेको पहिरोमा घरबास गुमाएका ३१ परिवारलाई एक वर्षपछि अस्थायी आवासमा सारिएको हो। गत आइतबार पीडितलाई अस्थायी आवास हस्तान्तरण गरिएको थियो।",
        "2021-08-09",
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['event_date_ad'] == '2020-08-14'



def test_extract_np_finds_explicit_municipality_in_followup_text() -> None:
    result = extract_np(
        'धुर्मुस–सुन्तली फाउण्डेशनद्वारा पहिरोपीडितलाई राहत वितरण',
        'कमलामाई नगरपालिका–६ निवासी पीडितलाई राहत वितरण गरिएको छ। साउन २८ गते बिहान २ बजे पहिरोमा घरसहित पुरिएर चार जनाको ज्यान गएको थियो।',
        '2017-08-22',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['municipality'] == 'Kamalamai Municipality'


def test_extract_np_prefers_event_district_municipality_over_other_district_mentions() -> None:
    result = extract_np(
        'रसुवामा पहिरो: ५ को मृत्यु , ४ बेपत्ता (अपडेट)',
        'रसुवाको टिमुरे बजार नजिक पहिरो खस्दा ५ जनाको ज्यान गएको छ। होटलमा बसेका सिन्धुपाल्चोकको भोटेकोशी गाउँपालिकाका श्याम श्रेष्ठ र रसुवाको गोसाइकुण्ड गाउँपालिका-१ का मिग्मार गुम्बुको मृत्यु भएको छ।',
        '2018-07-26',
        None,
        KEYWORDS_CFG,
        published_year_hint=2018,
    )
    assert result['district'] == 'Rasuwa'
    assert result['municipality'] == 'Gosaikunda Rural Municipality'





def test_extract_np_bihibar_variant_backshifts_previous_day() -> None:
    result = extract_np(
        'पहिरोले घर भत्किँदा दुईजनाको मृत्यु',
        'जिल्लाको जुनीजाँदे गाउँपालिका ६ छिर्कस्थित बिहिबार राति भक्तबहादुर बुढाको घर पहिरोले भत्काउँदा दुई जनाको मृत्यु भएको हो।',
        '2018-07-20',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2018-07-19'
    assert result['conf_date'] >= 0.78


def test_extract_np_raises_same_day_confidence_for_explicit_clock_time() -> None:
    result = extract_np(
        'पहिरोले बुटवल–पाल्पा सडकखण्ड अवरुद्ध',
        'सिद्धार्थ राजमार्गको बुटवल–पाल्पा सडकखण्डअन्तर्गत पाल्पाको दोभानमा दिउँसो ४ः०० बजे पहिरो खस्दा सडक अवरुद्ध भएको छ ।',
        '2017-08-02',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2017-08-02'
    assert result['conf_date'] >= 0.78

def test_extract_np_ward_form_municipality_without_suffix() -> None:
    result = extract_np(
        'बांगाबगरमा पहिरो : महाकाली राजमार्ग अवरुद्ध',
        'बैतडीको डिलाशैनी–६ बांगाबगरमा आज बिहान पहिरो जाँदा सडक अवरुद्ध भएको छ।',
        '2017-08-04',
        None,
        KEYWORDS_CFG,
        published_year_hint=2017,
    )
    assert result['municipality'] == 'Dilasaini Rural Municipality'


def test_extract_np_mangalbar_variant_backshifts_previous_day() -> None:
    result = extract_np(
        'बाजुरामा पहिरोले घर बगायो, गाउँ नै जोखिममा',
        'बाजुराको त्रिवेणी नगरपालिका–९ ताम्सुमा मङ्गलबार रातिदेखि निरन्तर वर्षाका कारण पहिरो आएर घर बगाएको हो।',
        '2020-07-29',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2020-07-28'
    assert result['conf_date'] >= 0.78


def test_extract_np_budhawar_variant_backshifts_previous_day() -> None:
    result = extract_np(
        'रुकुम पश्चिममा ढिस्कोले पुर्दा २ बालिकाको मृत्यु',
        'डिएसपीका अनुसार विक द्धयलाई बुधवार बेलुका साढे ५ बजेतिर ढिस्कोले पुरेको हो।',
        '2019-09-12',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2019-09-11'
    assert result['conf_date'] >= 0.78


def test_extract_np_saadhe_clock_time_raises_same_day_confidence() -> None:
    result = extract_np(
        'पहिरोले सडक अवरुद्ध',
        'सिद्धार्थ राजमार्गमा बेलुका साढे ५ बजेतिर पहिरो खस्दा सडक अवरुद्ध भएको छ।',
        '2019-09-12',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2019-09-12'
    assert result['conf_date'] >= 0.78


def test_extract_np_uses_wider_date_window_for_late_weekday_cue() -> None:
    filler = ' '.join(['विवरण'] * 120)
    text = f'{filler} आइतबार दिउँसो करिब १ बजे माथिबाट आएको पहिरोले तीन जनालाई पुरेको थियो।'
    result = extract_np(
        'पहिरोमा परेर रूकुम पश्चिममा आमा-छोरीको मृत्यु',
        text,
        '2022-08-29',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2022-08-28'
    assert result['conf_date'] >= 0.78


def test_extract_np_backshifts_gayeratidekhi_for_direct_road_closure_event() -> None:
    result = extract_np(
        'पहिरो खस्दा मध्यपहाडी लोकमार्ग अवरुद्ध',
        'अविरल वर्षासँगै सडकमाथि बाट आएको पहिरो खस्दा मध्यपहाडी पुष्पलाल लोकमार्ग गएरातिदेखि अवरुद्ध भएको छ।',
        '2020-07-10',
        None,
        KEYWORDS_CFG,
    )
    assert result['event_date_ad'] == '2020-07-09'
    assert result['conf_date'] >= 0.78


def test_extract_np_victims_home_district_does_not_relocate_the_event() -> None:
    """Regression: an excavator driver's home district became the event district.

    "गोरखाको सिरानचोक गाउँपालिका–१ केराबारीमा ... पहिरो" places the landslide in
    Gorkha. "सिन्धुपाल्चोक जिल्लाको मेलम्ची घर भएका चालक" is where the driver
    lived. Reading the second as the event location moved the event two
    districts away, and the resulting record was self-consistent, so nothing
    downstream could detect it.
    """

    result = extract_np(
        'गोरखामा पहिरोले पुरिएर स्काभेटरसहित चालक बेपत्ता',
        'गोरखाको सिरानचोक गाउँपालिका–१ केराबारीमा शुक्रबार बिहान गएको पहिरोले स्काभेटरसहित '
        'चालक पुरिएर बेपत्ता भएका छन् । गुप्चेखोला नजिकै बाटो खन्दै गरेको बेला सिन्धुपाल्चोक '
        'जिल्लाको मेलम्ची घर भएका चालक रमेश तामाङसहित स्काभेटरलाई माथिबाट खसेको माटोको '
        'ढिस्कोले पुरेको हो ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['district'] == 'Gorkha'


def test_extract_np_still_reads_a_plain_district_qualifier() -> None:
    """The guard must not suppress an ordinary "<X> जिल्ला" event mention."""

    result = extract_np(
        'सिन्धुपाल्चोकमा पहिरो',
        'सिन्धुपाल्चोक जिल्लाको जुगल गाउँपालिका–२ लिडीमा पहिरो खस्दा तीन जनाको मृत्यु भयो ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['district'] == 'Sindhupalchok'


def test_extract_np_reads_a_word_form_death_count() -> None:
    """Nepali writes small tolls as words; the patterns matched digits only."""

    result = extract_np(
        'बैतडीमा पहिरोले घर पुरिँदा तीन जनाको मृत्यु',
        'कैलाली । बैतडीमा पहिरोले घर पुरिदा तीन जनाको मृत्यु भएको छ । जिल्लाको '
        'शिवनाथ गाउँपालिका–६ मा पहिरोले घर पुरिदा तीन वर्षीया बालिकासहित तीन जनाको '
        'मृत्यु भएको हो ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['deaths'] == 3


def test_extract_np_reads_a_toll_from_a_body_recovery_sentence() -> None:
    """"शव फेला परेको" confirms a death without using any death term."""

    result = extract_np(
        'पहिराेमा बेपत्ता पाँचै जनाको शव भेटियो',
        'पाल्पा । रम्भा गाउँपालिका–२ बेलौजामा बिहीबार बिहान पहिराले घर पुरिँदा '
        'बेपत्ता भएका पाँच जनाको शव भेटिएको छ ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['deaths'] == 5


def test_extract_np_does_not_read_the_verb_cha_as_the_numeral_six() -> None:
    """`छ` is both "six" and the verb "is", so it needs a person classifier."""

    result = extract_np(
        'पहिरोले सडक अवरुद्ध',
        'पहिरोले सडक अवरुद्ध भएको छ । यातायात ठप्प छ । स्थानीय प्रशासन खटिएको छ ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert result['deaths'] is None


def test_extract_np_records_an_explicit_zero_but_never_imputes_one() -> None:
    stated = extract_np(
        'कर्णाली राजमार्गमा पहिरो, सयौं सवारीसाधन अलपत्र',
        'कर्णाली राजमार्गको कालिकोट खण्डमा पहिरो जाँदा सयौँ सवारीसाधन अलपत्र परेका '
        'छन् । पहिरोबाट मानवीय क्षति भएको छैन । उद्धारका लागि सुरक्षा निकाय खटिएका छन् ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert stated['deaths'] == 0

    silent = extract_np(
        'पहिरोले सडक अवरुद्ध',
        'पहिरोका कारण सडक अवरुद्ध भएको छ । सवारी साधन जाममा परेका छन् ।',
        '2021-07-30',
        None,
        KEYWORDS_CFG,
        published_year_hint=2021,
    )
    assert silent['deaths'] is None
