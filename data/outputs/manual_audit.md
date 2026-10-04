# Manual Audit Report

Generated at: 2026-04-20T13:57:10Z
Total rows: 200
Labeled rows: 200
Unlabeled rows: 0

## Snapshot Metrics
Classification macro F1: 0.656
District accuracy: 0.890625
Municipality accuracy: 0.8152173913043478
Date accuracy: 0.751937984496124
Deaths exact match: 0.509090909090909
Trigger accuracy: 0.6192893401015228

## Mismatch Summary
- class: 70 mismatches, 0 missing predictions, 200 labeled rows
- district: 14 mismatches, 4 missing predictions, 128 labeled rows
- municipality: 17 mismatches, 17 missing predictions, 92 labeled rows
- date: 32 mismatches, 3 missing predictions, 129 labeled rows
- deaths: 27 mismatches, 23 missing predictions, 55 labeled rows
- trigger: 27 mismatches, 3 missing predictions, 132 labeled rows

## Priority Rows
- P3: [online-khabar] ताप्लेजुङमा पहिरोले घर पुरिंदा ४ जना घाइते – Online Khabar (https://www.onlinekhabar.com/2025/07/1714207/4-injured-as-landslide-buries-house-in-taplejung)
  Issues: class 2 -> 1; date 2025-07-01 -> 2025-07-02; trigger unknown -> anthropogenic
- P3: [rising-nepal] Landslide obstructs North-South Road in Sankhuwasabha (https://risingnepaldaily.com/news/12383)
  Issues: class 2 -> 1; municipality <missing> -> Bhotkhola Rural Municipality
- P3: [setopati] दार्चुला हिमपहिरो: तीन जनाको शव फेला, दुई जना अझै बेपत्ता (https://www.setopati.com/social/301127)
  Issues: class 2 -> 1; municipality <missing> -> Byas Rural Municipality; deaths <missing> -> 3
- P3: [setopati] पहिरोले घर भत्किँदा पोखरामा तीन जना घाईते (https://www.setopati.com/social/73370)
  Issues: class 2 -> 1
- P3: [setopati] माटोको ढिस्को खसेर पुरिएका दुई जनालाई सेनाले गर्‍यो उद्धार (https://www.setopati.com/politics/380751)
  Issues: class 2 -> 1; trigger unknown -> anthropogenic
- P2: [ekantipur] डडेलधुरामा हाटबजार सञ्चालन गर्ने तयारी - कान्तिपुर (https://ekantipur.com/sudurpaschim-pradesh/2026/03/23/preparations-to-operate-a-market-in-dadeldhura-36-42.html)
  Issues: class 1 -> 3
- P2: [ekantipur] नदी दोहन गर्नेलाई कारबाही सिफारिस - कान्तिपुर (https://ekantipur.com/gandaki-pradesh/2026/03/25/action-recommended-against-those-exploiting-the-river-00-03.html)
  Issues: class 2 -> 3
- P2: [himalayan-times] 102 killed in Nepal floods, landslides in past one week: Govt - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/kathmandu/102-killed-floods-landslides-nepal-one-week)
  Issues: class 2 -> 3
- P2: [himalayan-times] 20 feared dead in remote India landslide - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/world/20-feared-dead-in-remote-india-landslide)
  Issues: class 2 -> 3
- P2: [himalayan-times] At least 485 Pyuthan families displaced by floods, landslides - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/least-485-pyuthan-families-displaced-floods-landslides)
  Issues: class 2 -> 3
- P2: [himalayan-times] Floods, landslides kill at least 43 people in Nepal - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/floods-landslides-kill-at-least-43-people-in-nepal)
  Issues: class 1 -> 3
- P2: [himalayan-times] Landslide obstructs Narayangadh-Muglin road again - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/landslide-obstructs-narayangadh-muglin-road-again)
  Issues: trigger unknown -> rainfall
- P2: [himalayan-times] Mudslide claims one in Dhading; one missing - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/mudslide-claims-one-in-dhading-one-missing)
  Issues: date 2021-06-20 -> 2021-06-18; trigger unknown -> anthropogenic
- P2: [himalayan-times] Obstructed Narayangadh-Muglin road reopens - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/landslide-obstructs-vehicular-movement-narayangadh-muglin-road)
  Issues: trigger unknown -> rainfall
- P2: [himalayan-times] Six of a family buried to death in Rolpa landslide - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/six-of-a-family-buried-to-death-in-rolpa-landslide)
  Issues: municipality <missing> -> Thasang Rural Municipality; deaths <missing> -> 6
- P2: [himalayan-times] Stranded!!! - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/multimedia/myagdi-landslide-obstructs-beni-jomsom-road-section)
  Issues: class 1 -> 2
- P2: [himalayan-times] Syangja landslide update: Four missing persons found dead - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/syangja-landslide-update-four-missing-persons-found-dead)
  Issues: class 1 -> 2; deaths 6 -> 4
- P2: [himalayan-times] Transportation resumes along Narayangadh-Muglin road section - The Himalayan Times - Nepal's No.1 English Daily Newspaper | Nepal News, Latest Politics, Business, World, Sports, Entertainment, Travel, Life Style News (https://thehimalayantimes.com/nepal/landslide-obstructs-narayangadh-muglin-road-section-2)
  Issues: class 1 -> 2
- P2: [kathmandu-post] Phewa Lake: PM’s push meets decades of encroachment, court orders, and costly reality (https://kathmandupost.com/national/2026/03/31/phewa-lake-pm-s-push-meets-decades-of-encroachment-court-orders-and-costly-reality)
  Issues: class 2 -> 3
- P2: [online-khabar] अब असोजसम्म गुड्दैनन् बागलुङका ग्रामीण सडकमा गाडी – Online Khabar (https://www.onlinekhabar.com/2023/07/1332020/%E0%A4%85%E0%A4%AC-%E0%A4%85%E0%A4%B8%E0%A5%8B%E0%A4%9C%E0%A4%B8%E0%A4%AE%E0%A5%8D%E0%A4%AE-%E0%A4%97%E0%A5%81%E0%A4%A1%E0%A5%8D%E0%A4%A6%E0%A5%88%E0%A4%A8%E0%A4%A8%E0%A5%8D-%E0%A4%AC%E0%A4%BE)
  Issues: class 2 -> 3
- P2: [online-khabar] एकतर्फी खुल्यो नारायणगढ-मुग्लिन सडकखण्ड – Online Khabar (https://www.onlinekhabar.com/2025/09/1769311/narayangadh-muglin-road-section-opened-to-one-way-traffic)
  Issues: class 1 -> 2; district Kathmandu -> Chitwan
- P2: [online-khabar] काठमाडौंको तारकेश्वरमा पहिरोले घर पुर्दा बाबु-छोरीको मृत्यु – Online Khabar (https://www.onlinekhabar.com/2023/08/1346522/%E0%A4%95%E0%A4%BE%E0%A4%A0%E0%A4%AE%E0%A4%BE%E0%A4%A1%E0%A5%8C%E0%A4%82%E0%A4%95%E0%A5%8B-%E0%A4%A4%E0%A4%BE%E0%A4%B0%E0%A4%95%E0%A5%87%E0%A4%B6%E0%A5%8D%E0%A4%B5%E0%A4%B0%E0%A4%AE%E0%A4%BE-%E0%A4%AA)
  Issues: date 2023-08-05 -> 2023-08-06; deaths <missing> -> 2
- P2: [online-khabar] काठमाडौंको धापासीमा पहिरोले सडक अवरुद्ध – Online Khabar (https://www.onlinekhabar.com/2025/08/1748581/landslide-blocks-road-in-dhapasi-kathmandu)
  Issues: class 1 -> 2; date 2025-08-22 -> 2025-08-23
- P2: [online-khabar] गुल्मीमा सुख्खा पहिरोमा एक महिला बेपत्ता – Online Khabar (https://www.onlinekhabar.com/2024/09/1543983/a-woman-is-missing-in-a-landslide-in-gulmi)
  Issues: municipality <missing> -> Malika Rural Municipality
- P2: [online-khabar] चार ठाउँमा खसेको पहिरोले पासाङल्हामु राजमार्ग अवरुद्ध – Online Khabar (https://www.onlinekhabar.com/2025/07/1714153/landslides-block-pasanglhamu-highway-in-four-places)
  Issues: class 1 -> 2
