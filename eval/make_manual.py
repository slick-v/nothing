"""Generate a fictional 100-page manual and its eval set (standard library only).

Run from anywhere:  python eval/make_manual.py
Writes ashgrove_manual.pdf and ashgrove_eval_set.json next to this file.
Page labels are found by searching each page's text for the evidence, never typed by hand.
"""
import json
import re
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOTAL_PAGES = 100
HEADER = "Ashgrove Regional Transit - Operations and Employee Manual - 2027 Edition"
LINES_PER_PAGE = 60

# ---------------------------------------------------------------- facts

DEPOTS = [
    # name, code, street, manager, safety officer, hours, bays, chargers, yard speed km/h, extension, local rule
    ("Larkfield", "LKF", "14 Quarry Road", "Imani Okafor", "Tomasz Wrona", "04:30 to 00:45", 62, 18, 12, 4101, "Buses over 12 metres must enter through Gate B because Gate A has a 3.4 metre height bar."),
    ("Tolland", "TLD", "220 Mill Lane", "Rafael Quintero", "Saoirse Byrne", "04:15 to 01:00", 88, 44, 10, 4102, "The wash line closes every Tuesday from 09:00 to 12:00 for water recycling checks."),
    ("Corran Street", "CRS", "3 Corran Street", "Mei-Ling Hsu", "Adebayo Lawal", "05:00 to 23:30", 41, 12, 8, 4103, "Reversing in the north yard requires a banksman at all times because of the school next door."),
    ("Penhale", "PNH", "77 Harbour View", "Dmitri Volkov", "Aisha Rahman", "04:45 to 00:15", 53, 20, 15, 4104, "Salt spray rinses are required weekly for every vehicle parked in the seaward row."),
    ("Wexcombe", "WXC", "9 Beacon Hill", "Nadia Haddad", "Callum Reid", "05:15 to 23:45", 37, 8, 9, 4105, "Winter chains are stored in Container 6 and must be signed out from the duty controller."),
    ("Marlstone", "MLS", "151 Foundry Way", "Oluwaseun Adeyemi", "Greta Lindqvist", "04:00 to 01:15", 96, 52, 11, 4106, "The heavy lift hoist in Bay 40 may only be used by staff who hold certificate TR-305."),
    ("Ferndown Park", "FDP", "68 Orchard Rise", "Hannah Weiss", "Kenji Morimoto", "05:30 to 23:15", 29, 6, 7, 4107, "Engines must be switched off within 2 minutes of parking under the local air quality agreement."),
    ("Glenarrow", "GLN", "402 Viaduct Road", "Santiago Rojas", "Fatima Zahra", "04:20 to 00:50", 71, 30, 13, 4108, "Drivers must sound no horn in the yard between 22:00 and 06:00 under the residents' agreement."),
    ("Bramwell", "BRW", "25 Canal Wharf", "Priyanka Menon", "Lucas Ferreira", "04:50 to 00:30", 58, 24, 14, 4109, "The canal gate is locked during flood alerts and vehicles must use the Station Road exit."),
    ("Sutter Cross", "STX", "88 Market Row", "Elias Johansson", "Chidinma Eze", "05:10 to 23:50", 33, 10, 6, 4110, "Market day deliveries block the east entrance every Saturday until 11:30."),
    ("Oakhampton", "OKH", "510 Airfield Drive", "Zanele Dlamini", "Marek Novak", "03:55 to 01:30", 104, 60, 16, 4111, "Airport shuttle vehicles are parked in Row K and must never be reassigned without approval."),
    ("Thornbury Vale", "TBV", "19 Copper Lane", "Yusuf Demir", "Isla Campbell", "05:20 to 23:20", 45, 16, 10, 4112, "Fuel deliveries arrive on Thursdays at 07:30 and the south lane is closed for 40 minutes."),
]

ROUTES = [
    # number, from, to, depot, class, peak minutes, off-peak minutes, first, last
    (3, "Harbour View", "Central Station", "Penhale", "AT-3A", 6, 12, "05:05", "00:10"),
    (5, "Quarry Road", "University", "Larkfield", "AT-4B", 8, 15, "05:20", "23:55"),
    (7, "Mill Lane", "Riverside", "Tolland", "AT-5E", 5, 10, "04:50", "00:30"),
    (9, "Corran Street", "Old Town", "Corran Street", "AT-2M", 12, 20, "05:45", "23:10"),
    (11, "Beacon Hill", "Central Station", "Wexcombe", "AT-3A", 15, 30, "06:00", "22:40"),
    (14, "Foundry Way", "Eastgate Mall", "Marlstone", "AT-6D", 4, 9, "04:35", "00:55"),
    (16, "Orchard Rise", "City Hospital", "Ferndown Park", "AT-2M", 10, 20, "05:50", "22:55"),
    (18, "Viaduct Road", "Northern Terminal", "Glenarrow", "AT-5E", 7, 14, "04:55", "00:25"),
    (22, "Canal Wharf", "Technology Park", "Bramwell", "AT-7C", 9, 18, "05:15", "23:35"),
    (24, "Market Row", "Westfield", "Sutter Cross", "AT-4B", 11, 22, "05:40", "23:05"),
    (27, "Airfield Drive", "International Airport", "Oakhampton", "AT-8X", 13, 13, "03:58", "01:22"),
    (29, "Copper Lane", "Central Station", "Thornbury Vale", "AT-3A", 14, 25, "05:35", "22:50"),
    (31, "Quarry Road", "Lakeside", "Larkfield", "AT-2M", 16, 32, "06:05", "22:20"),
    (33, "Mill Lane", "Southern Cross", "Tolland", "AT-6D", 6, 11, "04:40", "00:40"),
    (36, "Foundry Way", "Stadium", "Marlstone", "AT-7C", 8, 16, "05:10", "00:05"),
    (38, "Viaduct Road", "Kingsway", "Glenarrow", "AT-4B", 10, 19, "05:25", "23:45"),
    (41, "Canal Wharf", "Ferry Terminal", "Bramwell", "AT-3A", 17, 34, "06:15", "22:10"),
    (44, "Airfield Drive", "Business Park", "Oakhampton", "AT-5E", 12, 24, "05:00", "23:30"),
    (47, "Harbour View", "Marina", "Penhale", "AT-2M", 20, 40, "06:30", "21:45"),
    (52, "Copper Lane", "Hillcrest", "Thornbury Vale", "AT-4B", 18, 36, "06:20", "22:05"),
]

FLEET = [
    # class, description, seats, standing, length m, energy, inspection km, brake overhaul km, entered service
    ("AT-2M", "midi bus for narrow streets", 24, 18, 8.9, "diesel, 180 litre tank", 12000, 70000, 2019),
    ("AT-3A", "standard single-deck diesel bus", 38, 32, 11.9, "diesel, 260 litre tank", 15000, 90000, 2017),
    ("AT-4B", "standard single-deck hybrid bus", 36, 34, 12.1, "hybrid, 210 litre tank and 28 kWh battery", 18000, 110000, 2020),
    ("AT-5E", "standard single-deck electric bus", 34, 36, 12.0, "electric, 422 kWh battery", 25000, 140000, 2022),
    ("AT-6D", "double-deck diesel bus", 78, 22, 10.8, "diesel, 340 litre tank", 14000, 85000, 2018),
    ("AT-7C", "articulated electric bus", 51, 74, 18.2, "electric, 640 kWh battery", 22000, 125000, 2023),
    ("AT-8X", "airport shuttle coach with luggage racks", 44, 12, 13.2, "electric, 560 kWh battery", 30000, 160000, 2024),
    ("AT-1V", "accessible minivan for on-demand services", 8, 0, 5.9, "electric, 74 kWh battery", 20000, 60000, 2021),
]

PAY = [("G1", "18.40"), ("G2", "20.15"), ("G3", "22.30"), ("G4", "24.60"), ("G5", "27.05"), ("G6", "29.80"), ("G7", "33.25"), ("G8", "37.90")]

PROCEDURES = [
    ("SR-402", "Flooded roads", "Do not enter standing water deeper than 15 centimetres.", "Report the location to the control room and wait for a diversion instruction."),
    ("SR-405", "Snow and ice", "Reduce speed to no more than 30 km/h on untreated roads.", "Fit chains only at a designated stopping place with hazard lights on."),
    ("SR-409", "Vehicle fire", "Evacuate all passengers to a point at least 50 metres upwind of the vehicle.", "Use the extinguisher only if the fire is small and an exit stays clear behind you."),
    ("SR-412", "Fuel spills", "Contain any spill larger than 5 litres with the absorbent kit from the depot store.", "Notify the environmental coordinator within 30 minutes of the spill."),
    ("SR-417", "High winds", "Double-deck vehicles must stop crossing exposed bridges when gusts exceed 85 km/h.", "Single-deck services may continue on those bridges until gusts exceed 110 km/h."),
    ("SR-421", "Passenger medical emergency", "Stop at the nearest safe place and call the control room on Channel 2.", "Automatic defibrillators are carried on every AT-8X and AT-7C vehicle."),
    ("SR-423", "Battery thermal event", "Move at least 75 metres away from any electric vehicle showing battery smoke.", "Isolation may be carried out only by a technician who has completed TR-211."),
    ("SR-428", "Aggressive passengers", "Do not attempt physical removal of a passenger under any circumstances.", "Press the silent alarm and keep the doors unlocked unless told otherwise by police."),
    ("SR-431", "Lone working at night", "Staff working alone after 22:00 must check in with the controller every 60 minutes.", "A missed check-in triggers a welfare call within 10 minutes."),
    ("SR-436", "Collisions", "Photograph the scene and record the names of all witnesses before moving the vehicle.", "The driver must complete form IR-7 before the end of the shift."),
    ("SR-440", "Pedestrian strike", "Keep the vehicle in position and do not move it unless police instruct you to.", "A trained peer supporter is offered to the driver within 24 hours."),
    ("SR-444", "Hazardous items on board", "Refuse carriage of any fuel container larger than 5 litres.", "Unattended bags are reported using the code word Harbour on Channel 1."),
    ("SR-449", "Wheelchair ramp failure", "Manually deploy the ramp using the release lever under the floor panel.", "The vehicle must be taken out of service at the end of that trip."),
    ("SR-453", "Depot vehicle movements", "High-visibility clothing is mandatory at all times in every depot yard.", "Pedestrians have priority on the marked green walkways."),
    ("SR-458", "Charging equipment faults", "Never unplug a connector that shows a red fault light.", "Press the emergency stop and call the energy desk on extension 4190."),
    ("SR-462", "Heat stress", "Cab temperatures above 32 degrees Celsius must be reported to the controller.", "Drivers are allowed an extra 10 minute cooling break on such days."),
]

COURSES = [
    ("TR-101", "Induction and network knowledge", "5 days", "Every new employee", "no renewal"),
    ("TR-118", "Customer care and conflict awareness", "2 days", "All customer-facing staff", "every 3 years"),
    ("TR-126", "Accessible travel awareness", "1 day", "All drivers and inspectors", "every 2 years"),
    ("TR-140", "Defensive driving", "3 days", "All drivers", "every 4 years"),
    ("TR-203", "Electric vehicle operation", "4 days", "Drivers rostered on AT-5E, AT-7C or AT-8X", "every 5 years"),
    ("TR-211", "High-voltage isolation", "6 days", "Maintenance technicians", "every 2 years"),
    ("TR-218", "First aid at work", "3 days", "At least one person per shift in every depot", "every 3 years"),
    ("TR-305", "Heavy lift hoist operator", "2 days", "Technicians working in Marlstone Bay 40", "every 18 months"),
    ("TR-322", "Articulated vehicle conversion", "7 days", "Drivers moving to the AT-7C", "no renewal"),
    ("TR-340", "Duty controller certificate", "10 days", "Staff promoted to duty controller", "every 3 years"),
    ("TR-355", "Incident investigation", "4 days", "Safety officers and depot managers", "every 5 years"),
    ("TR-410", "Coach handling for airport services", "2 days", "Drivers rostered on Route 27", "every 4 years"),
]

# ---------------------------------------------------------------- page writing


def para(*sentences):
    return " ".join(sentences)


def depot_pages(i, d):
    name, code, street, manager, safety, hours, bays, chargers, speed, ext, rule = d
    routes = [r for r in ROUTES if r[3] == name]
    route_text = ", ".join(f"Route {r[0]}" for r in routes)
    first = [
        f"# 1.{i + 1} {name} Depot",
        para(f"{name} Depot (depot code {code}) is located at {street}.", f"The {name} depot manager is {manager}.",
             f"The {name} safety officer is {safety}.", f"The {name} gatehouse is staffed from {hours}, seven days a week."),
        para(f"{name} has {bays} parking bays.", f"{name} has {chargers} charging points.",
             f"The speed limit inside the {name} yard is {speed} km/h.", f"The {name} duty desk is reached on extension {ext}."),
        para(f"Services operated from {name} are {route_text}.", "Rosters are published on the staff portal every second Thursday and printed copies are displayed in the mess room."),
        para("All staff entering the yard sign in at the gatehouse using a personal identity card.",
             "Visitors are escorted at all times and are issued with a temporary pass that must be returned before leaving the site.",
             "Contractors must show a current site induction record before any work begins, and the record is checked against the contractor register held by the duty desk."),
        para("Vehicles returning at the end of service are refuelled or placed on charge, cleaned, and parked according to the allocation sheet for the following morning.",
             "Any defect noticed during the shift is written on the defect card and handed to the night maintenance team, who decide whether the vehicle is fit for the next duty."),
    ]
    second = [
        f"## {name} Depot local operating notes",
        f"Local rule at {name}: {rule}",
        para("Local rules are agreed between the depot manager and the safety officer and are reviewed at the quarterly depot safety meeting.",
             "Changes take effect only after they have been posted on the depot notice board for seven days.",
             "If a local rule appears to conflict with a procedure in Part 5 of this manual, the stricter of the two applies until the safety team has given a ruling."),
        para("The mess room is open throughout gatehouse hours and contains lockers, a kitchen area and a quiet room.",
             "Lockers are allocated by the duty desk and are emptied after an employee has left the depot.",
             "Personal items are left at the owner's risk, and valuables should not be kept in vehicles at any time."),
        para("New drivers complete a route familiarisation drive for each service operated from the depot before taking passengers.",
             "A driver who has not operated a route for six months repeats the familiarisation drive before returning to that route.",
             "Records of these drives are held by the duty desk and are checked when rosters are prepared."),
        para("The first vehicle of the morning undergoes a walk-round check witnessed by the shift supervisor.",
             "The check covers tyres, lights, mirrors, doors, the ramp and the emergency exits.",
             "Later vehicles are checked by the driver alone and the result is recorded on the handheld ticket machine."),
        para("Waste oil, coolant and tyres are stored in the marked compound and collected by an approved contractor.",
             "Spills are dealt with according to the procedures in Part 5, and the depot keeps absorbent materials next to each fuelling point."),
    ]
    return [first, second]


def route_pages():
    pages = []
    for p in range(10):
        pair = ROUTES[p * 2:p * 2 + 2]
        lines = [f"# 2.{p + 1} Routes {pair[0][0]} and {pair[1][0]}"]
        for n, a, b, depot, cls, peak, off, first, last in pair:
            lines += [
                f"## Route {n}: {a} to {b}",
                para(f"Route {n} runs between {a} and {b} and is operated from {depot} Depot.",
                     f"Route {n} is normally worked by class {cls} vehicles.",
                     f"Route {n} runs every {peak} minutes at peak times and every {off} minutes off-peak.",
                     f"The first departure on Route {n} is at {first} and the last departure is at {last}."),
                para("Peak times are 07:00 to 09:30 and 16:00 to 18:30 on weekdays.",
                     "Weekend timetables follow the off-peak frequency throughout the day unless a special event notice has been issued.",
                     "Drivers must not depart a timing point early, and a departure more than 5 minutes late is reported to the controller."),
                para("Layover time at each terminal is used for a walk-round check, and passengers may remain on board if the driver stays with the vehicle.",
                     "Diversions are announced by the controller over the radio and shown on the ticket machine display."),
            ]
        pages.append(lines)
    return pages


def fleet_pages():
    pages = []
    for i, (cls, desc, seats, standing, length, energy, inspect, brake, year) in enumerate(FLEET):
        pages.append([
            f"# 3.{i + 1} Vehicle class {cls}",
            para(f"Class {cls} is a {desc}.", f"Class {cls} entered service in {year}.", f"Class {cls} seats {seats} passengers and carries up to {standing} standing passengers.",
                 f"The overall length of class {cls} is {length} metres.", f"The energy system of class {cls} is {energy}."),
            para(f"Class {cls} receives a scheduled inspection every {inspect} km.", f"Brake overhaul on class {cls} takes place every {brake} km.",
                 "Scheduled inspections are booked through the maintenance planning system and take priority over service allocation when a vehicle is within 500 km of its limit."),
            para("Drivers may operate a vehicle class only after completing the training listed for it in Part 6.",
                 "The driver's cab has a seat adjustment guide on the door pillar, and drivers should adjust the seat and mirrors before moving off.",
                 "Warning lights on the dashboard are grouped into amber lights, which must be reported at the end of the trip, and red lights, which require the vehicle to be stopped as soon as it is safe."),
            para("Wheel nuts are checked by the maintenance team after any wheel change and again after the next 100 km of service.",
                 "Tyres are replaced when tread depth reaches the limit set by the maintenance planning system, and regrooved tyres are never fitted to the front axle.",
                 "Interior cleaning is carried out every night, with a deep clean every 28 days."),
            para("Passenger information screens are updated automatically each night at the depot.",
                 "If a screen is faulty the driver must make route announcements by voice.",
                 "All vehicles carry a fire extinguisher, a first aid kit, a high-visibility vest and an emergency hammer at each marked exit."),
        ])
    return pages


def pay_pages():
    table = [f"Grade {g} hourly rate: ${rate}." for g, rate in PAY]
    return [
        ["# 4.1 Pay grades", "Hourly rates apply from 1 January 2027 and are paid every four weeks into the employee's nominated account.", *table,
         "Employees move up one pay grade after completing the qualifying service and any training required for the higher grade. Pay statements are available on the staff portal three working days before payment."],
        ["# 4.2 Overtime", "Overtime is any time worked beyond the rostered shift and must be approved by the duty controller.",
         "The first 4 hours of overtime in a week are paid at 1.5 times the hourly rate.", "Overtime beyond the first 4 hours in a week is paid at 2 times the hourly rate.",
         "Time off in lieu may be chosen instead of overtime pay and must be taken within 8 weeks. No employee may work more than 12 hours of overtime in a single week without written approval from the depot manager."],
        ["# 4.3 Shift premiums", "A Sunday premium of $4.75 per hour is paid for all hours worked on a Sunday.", "A night premium of $2.40 per hour is paid for hours worked between 22:00 and 05:00.",
         "A split-shift allowance of $11.50 is paid for each duty with an unpaid break of more than 2 hours.", "Premiums are added to the hourly rate after overtime is calculated and are not themselves multiplied."],
        ["# 4.4 Annual leave", "Employees with less than 5 years of service receive 25 days of annual leave.", "Employees with 5 to 14 years of service receive 28 days of annual leave.", "Employees with 15 or more years of service receive 32 days of annual leave.",
         "Leave requests for the summer period must be made by 31 March. Up to 5 unused days may be carried into the next leave year with the approval of the depot manager."],
        ["# 4.5 Sickness absence", "Employees must notify the duty controller no later than 90 minutes before the start of a rostered shift when absent through illness.",
         "A doctor's certificate is required for any absence longer than 7 calendar days.", "Full sick pay is paid for the first 13 weeks of absence in any rolling 12 months.", "Half pay is paid for the following 13 weeks. A return-to-work conversation takes place on the first day back."],
        ["# 4.6 Family leave", "Parental leave is 16 weeks at full pay for any employee with at least 12 months of service.", "Bereavement leave is 5 days for a close family member.", "Carers may take up to 10 days of unpaid leave in any calendar year. Requests are made through the staff portal and are treated confidentially by the human resources team."],
        ["# 4.7 Pension", "Employees contribute 7% of pensionable pay to the pension plan.", "Ashgrove Regional Transit contributes 9% of pensionable pay.", "Employees join automatically after 3 months of service and may opt out in writing at any time. Benefit statements are issued each June."],
        ["# 4.8 Uniform", "New employees receive two shirts, two pairs of trousers and one jacket.", "Uniform items are replaced every 24 months or sooner if damaged at work.", "Safety boots are provided for depot staff and maintenance technicians. Uniform must be returned when employment ends."],
        ["# 4.9 Expenses", "Meal allowance of $14.00 is paid when a duty keeps an employee away from the home depot for more than 10 hours.", "Mileage for approved travel in a private car is paid at $0.62 per km.", "Expense claims must be submitted within 60 days through the staff portal, with receipts attached for anything over $25.00."],
        ["# 4.10 Free travel", "Employees travel free on all Ashgrove services on production of a staff pass.", "One nominated household member receives a companion pass after 2 years of service.", "Passes are the property of the company and must be surrendered on leaving. Misuse of a pass is a disciplinary matter under Part 8."],
    ]


def safety_pages():
    pages = []
    for i, (code, title, a, b) in enumerate(PROCEDURES):
        pages.append([
            f"# 5.{i + 1} Procedure {code}: {title}",
            f"Under procedure {code}: {a}", f"Also under procedure {code}: {b}",
            para("Every employee must know where this procedure applies and must follow it without waiting for instructions when immediate action is needed.",
                 "As soon as it is safe to do so, tell the control room what has happened, where you are, and whether anyone has been hurt."),
            para("The control room records the time of the call and decides whether to send a supervisor, stop other services, or contact the emergency services.",
                 "Do not speak to the media or post about the event on social media. Refer all questions to the communications team."),
            para("After the event, the depot safety officer reviews what happened and decides whether a formal investigation is required under Part 8.",
                 "Lessons learned are shared at the next depot safety meeting so that other teams can benefit from them."),
            para("Employees are protected from blame when they stop work in good faith because they believed there was a serious risk.",
                 "Concerns can also be raised confidentially with any safety officer or through the staff portal."),
        ])
    return pages


def training_pages():
    pages = []
    for p in range(8):
        lines = [f"# 6.{p + 1} Training courses"]
        for code, title, days, who, renew in COURSES[p * 12 // 8:(p + 1) * 12 // 8]:
            refresh = "This course has no renewal." if renew == "no renewal" else f"Course {code} must be renewed {renew}."
            lines += [f"## Course {code}: {title}", para(f"Course {code} lasts {days}.", f"Course {code} is required for: {who}.", refresh)]
        lines += [
            para("Courses are booked through the staff portal by the depot manager, and attendance counts as paid working time.",
                 "Employees who miss a booked course without good reason may be removed from duties that depend on it."),
            para("Certificates are recorded in the training register, and reminders are sent 90 days before a renewal falls due.",
                 "An employee whose certificate has expired may not carry out the related duties until it has been renewed."),
            para("Trainers assess every candidate on both practical skill and written understanding.",
                 "A candidate who does not pass may repeat the assessment once without charge after further coaching."),
        ]
        pages.append(lines)
    return pages


def fare_pages():
    return [
        ["# 7.1 Fare zones", "The network is divided into 4 fare zones.", "A single adult fare within one zone costs $2.30.", "A single adult fare across two zones costs $3.10.", "A single adult fare across three zones costs $3.85.", "A single adult fare across all four zones costs $4.60.", "Airport Route 27 has a separate flat fare of $9.50."],
        ["# 7.2 Passes", "A day pass valid in all zones costs $8.20.", "A weekly pass valid in all zones costs $31.00.", "A monthly pass valid in all zones costs $112.00.", "Passes are valid on all routes except Route 27, which needs an airport supplement of $5.00. Passes are loaded onto a travel card or the Ashgrove app."],
        ["# 7.3 Concessions", "Children under 5 travel free with a fare-paying adult.", "Passengers aged 5 to 15 pay 50% of the adult fare.", "Passengers aged 65 or over travel free after 09:30 on weekdays and all day at weekends.", "Registered students receive 25% off weekly and monthly passes. Concession holders must show a valid card when asked."],
        ["# 7.4 Penalty fares", "The penalty fare for travelling without a valid ticket is $60.", "The penalty fare is reduced to $30 when paid within 14 days.", "Inspectors must issue a written notice and must not ask for cash on the vehicle. Appeals are made in writing within 21 days to the revenue protection office."],
        ["# 7.5 Refunds and lost property", "Unused monthly passes are refunded in full if returned within 7 days of purchase.", "Items left on vehicles are kept at the Central Station lost property office for 28 days.", "Unclaimed items are donated to charity or disposed of securely after that period. Perishable items are thrown away at the end of the working day."],
        ["# 7.6 Cash handling", "Drivers may accept cash only up to $20 for any single fare payment.", "Cash floats of $40 are issued at the start of each duty and paid in at the end of it.", "Differences of more than $5 are investigated by the revenue office. Drivers must not give credit or accept foreign currency."],
    ]


def conduct_pages():
    extra = para("Records of these matters are kept securely by the human resources team and are available only to those who need them to carry out their duties.",
                 "Employees may ask to see the records held about them at any time.")
    return [
        ["# 8.1 Incident reporting", "All incidents are reported on form IR-7 before the end of the shift.", "Near misses are reported on form NM-2 within 48 hours.", "Injuries needing hospital treatment must be phoned to the safety director within 1 hour.", extra],
        ["# 8.2 Investigation", "Formal investigations must be completed within 30 calendar days.", "An employee may be accompanied by a colleague or union representative at any investigation meeting.", "Findings are shared with the employee in writing within 5 working days of completion.", extra],
        ["# 8.3 Disciplinary warnings", "A first written warning stays on file for 12 months.", "A final written warning stays on file for 24 months.", "Dismissal may follow a further offence during the life of a final written warning.", extra],
        ["# 8.4 Appeals", "An appeal against any disciplinary decision must be lodged within 10 working days.", "Appeals are heard by a manager who has had no earlier involvement in the case.", "The outcome of the appeal is final and is given in writing.", extra],
        ["# 8.5 Alcohol and drugs", "The alcohol limit for all safety-critical staff is 0.2 grams per litre of blood.", "Random testing is carried out on at least 10% of safety-critical staff each year.", "Testing also takes place after any collision that causes injury.", extra],
        ["# 8.6 Mobile devices", "Drivers must not use a handheld phone while in the cab, even when the vehicle is stationary at a stop.", "Phones must be switched to silent and stored in the driver's bag during a duty.", "A breach is treated as a serious offence.", extra],
        ["# 8.7 Driving hours", "Drivers may not drive for more than 4 hours and 30 minutes without a break of at least 30 minutes.", "The maximum driving time in any one duty is 9 hours.", "A minimum rest of 11 hours is required between duties.", extra],
        ["# 8.8 Grievances", "A grievance should first be raised informally with the employee's line manager.", "A formal grievance receives a written response within 15 working days.", "Grievances about a line manager are handled by the depot manager of another depot.", extra],
    ]


def amendment_pages():
    return [
        ["# 9.1 Amendment 1", "Amendment 1 takes effect from 1 February 2027.", "Amendment 1 changes the deep clean cycle for electric vehicles.", "Electric vehicles now receive a deep clean every 21 days instead of every 28 days.",
         "All amendments in this part replace any conflicting text elsewhere in this manual, and depot managers must brief their teams within 14 days of an amendment taking effect."],
        ["# 9.2 Amendment 2", "Amendment 2 takes effect from 1 March 2027.", "Amendment 2 replaces the night premium in section 4.3.", "The night premium is now $3.10 per hour instead of the earlier rate.",
         "The change applies to all hours worked between 22:00 and 05:00 on or after the effective date, and no back pay is due for earlier periods."],
        ["# 9.3 Amendment 3", "Amendment 3 takes effect from 1 April 2027.", "Amendment 3 replaces the penalty fare in section 7.4.", "The penalty fare for travelling without a valid ticket is now $75, or $40 when paid within 14 days.",
         "Notices issued before the effective date remain payable at the amounts printed on them, and inspectors have been issued with new notice books."],
    ]


def glossary_pages():
    return [
        ["# 10.1 Glossary A to H", "Banksman: a person who guides a vehicle while it is reversing.", "Defect card: the paper record of a fault found during a duty.", "Duty controller: the person responsible for a depot's live service during a shift.", "Energy desk: the team that manages charging across all depots.", "Headway: the time between two vehicles on the same route."],
        ["# 10.2 Glossary I to R", "Layover: time spent at a terminal between trips.", "Near miss: an event that could have caused harm but did not.", "Roster: the published schedule of an employee's duties.", "Revenue protection: the team that checks tickets and handles penalty fares."],
        ["# 10.3 Glossary S to Z", "Split shift: a duty containing an unpaid break of more than 2 hours.", "Staff portal: the website used for rosters, pay statements, leave and training bookings.", "Timing point: a stop where a vehicle must not depart early.", "Walk-round check: a visual safety check of the vehicle before service."],
        ["# 10.4 Central contacts", "Control room: extension 4000, staffed 24 hours a day.", "Safety director: Beatriz Monteiro, extension 4020.", "Head of human resources: Samuel Oyelaran, extension 4030.", "Environmental coordinator: Linnea Berg, extension 4040.", "Head of revenue protection: Arjun Bhatt, extension 4050."],
    ]


def build_pages():
    parts = [("Part 1: Depots", [p for i, d in enumerate(DEPOTS) for p in depot_pages(i, d)]),
             ("Part 2: Routes", route_pages()), ("Part 3: Fleet", fleet_pages()), ("Part 4: Pay, leave and benefits", pay_pages()),
             ("Part 5: Safety procedures", safety_pages()), ("Part 6: Training", training_pages()), ("Part 7: Fares and revenue", fare_pages()),
             ("Part 8: Conduct and incidents", conduct_pages()), ("Part 9: Amendments", amendment_pages()), ("Part 10: Glossary and contacts", glossary_pages())]
    contents, number = ["# Contents"], 4
    for title, pages in parts:
        contents.append(f"{title} ........ page {number}")
        number += len(pages)
    pages = [
        ["# Ashgrove Regional Transit", "Operations and Employee Manual", "2027 Edition",
         "Ashgrove Regional Transit is a fictional organisation. This document was generated for testing retrieval systems, and any resemblance to a real organisation or person is accidental."],
        contents,
        ["# How to use this manual", "This manual applies to all employees of Ashgrove Regional Transit. Parts 1 to 3 describe depots, routes and vehicles. Part 4 covers pay and leave. Parts 5 and 8 cover safety and conduct.",
         "Part 9 contains amendments. When an amendment conflicts with an earlier section, the amendment applies.", "Questions about this manual should be sent to the safety director or the head of human resources, whose contacts are listed in section 10.4."],
    ]
    for _, part in parts:
        pages += part
    assert len(pages) == TOTAL_PAGES, len(pages)
    return pages


def write_pdf(pages, path):
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
            3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"}
    kids, n = [], 5
    for number, blocks in enumerate(pages, start=1):
        ops = ["BT 40 800 Td 12 TL /F1 8 Tf", f"({escape(HEADER)}) Tj T* T*"]
        used = 0
        for block in blocks:
            if block.startswith("#"):
                big = block.startswith("# ")
                ops += ["T*", f"/F2 {14 if big else 11} Tf", f"({escape(block.lstrip('# '))}) Tj T* T*", "/F1 10 Tf"]
                used += 4
            else:
                wrapped = textwrap.wrap(block, 98)
                ops += ["/F1 10 Tf"] + [f"({escape(line)}) Tj T*" for line in wrapped] + ["T*"]
                used += len(wrapped) + 1
        assert used <= LINES_PER_PAGE, (number, used)
        ops.append("ET")
        ops.append(f"BT /F1 8 Tf 280 24 Td (Page {number} of {TOTAL_PAGES}) Tj ET")
        body = "\n".join(ops).encode("latin-1")
        objs[n] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body)
        objs[n + 1] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                       b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % n)
        kids.append(n + 1)
        n += 2
    objs[2] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), b" ".join(b"%d 0 R" % k for k in kids))
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for i in sorted(objs):
        offsets[i] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (i, objs[i])
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for i in sorted(objs):
        out += b"%010d 00000 n \n" % offsets[i]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))


def escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# ---------------------------------------------------------------- questions
# (type, question, expected answer, must_include, evidence sentences)

Q = [
    # fact
    ("fact", "Who is the safety director?", "Beatriz Monteiro.", [["Monteiro"]], ["Safety director: Beatriz Monteiro"]),
    ("fact", "How long does the Duty controller certificate course last?", "10 days.", [["10 days", "ten days"]], ["Course TR-340 lasts 10 days."]),
    ("fact", "How many fare zones does the network have?", "4.", [["4", "four"]], ["The network is divided into 4 fare zones."]),
    ("fact", "What is the extension for the control room?", "4000.", [["4000"]], ["Control room: extension 4000"]),
    ("fact", "How much does the employer contribute to the pension?", "9% of pensionable pay.", [["9%", "9 percent"]], ["Ashgrove Regional Transit contributes 9% of pensionable pay."]),
    ("fact", "How many weeks of parental leave at full pay are employees entitled to?", "16 weeks.", [["16 weeks", "sixteen weeks"]], ["Parental leave is 16 weeks at full pay"]),
    ("fact", "How much is the meal allowance?", "$14.00.", [["14.00", "$14"]], ["Meal allowance of $14.00"]),
    ("fact", "What year did class AT-5E enter service?", "2022.", [["2022"]], ["Class AT-5E entered service in 2022."]),
    # similar_facts: the same kind of fact exists for every depot, route or class
    ("similar_facts", "Who is the depot manager at Glenarrow?", "Santiago Rojas.", [["Rojas"]], ["The Glenarrow depot manager is Santiago Rojas."]),
    ("similar_facts", "Who is the safety officer at Bramwell?", "Lucas Ferreira.", [["Ferreira"]], ["The Bramwell safety officer is Lucas Ferreira."]),
    ("similar_facts", "How many charging points does Tolland have?", "44.", [["44"]], ["Tolland has 44 charging points."]),
    ("similar_facts", "What is the yard speed limit at Sutter Cross?", "6 km/h.", [["6 km/h", "6 kilometres", "6 kph"]], ["The speed limit inside the Sutter Cross yard is 6 km/h."]),
    ("similar_facts", "How many parking bays does the Wexcombe depot have?", "37.", [["37"]], ["Wexcombe has 37 parking bays."]),
    ("similar_facts", "How often does Route 33 run at peak times?", "Every 6 minutes.", [["6 minutes", "six minutes"]], ["Route 33 runs every 6 minutes at peak times"]),
    ("similar_facts", "What time is the last departure on Route 41?", "22:10.", [["22:10"]], ["The first departure on Route 41 is at 06:15 and the last departure is at 22:10."]),
    ("similar_facts", "How often is class AT-6D inspected?", "Every 14,000 km.", [["14000", "14,000"]], ["Class AT-6D receives a scheduled inspection every 14000 km."]),
    ("similar_facts", "What is the brake overhaul interval for class AT-8X?", "Every 160,000 km.", [["160000", "160,000"]], ["Brake overhaul on class AT-8X takes place every 160000 km."]),
    # table style values
    ("table", "What is the hourly rate for grade G6?", "$29.80.", [["29.80"]], ["Grade G6 hourly rate: $29.80."]),
    ("table", "How much is a single adult fare across three zones?", "$3.85.", [["3.85"]], ["A single adult fare across three zones costs $3.85."]),
    ("table", "How much does a monthly pass cost?", "$112.00.", [["112"]], ["A monthly pass valid in all zones costs $112.00."]),
    ("table", "How many days of annual leave does someone with 8 years of service get?", "28 days.", [["28"]], ["Employees with 5 to 14 years of service receive 28 days of annual leave."]),
    ("table", "What is the alcohol limit for safety-critical staff?", "0.2 grams per litre of blood.", [["0.2"]], ["The alcohol limit for all safety-critical staff is 0.2 grams per litre of blood."]),
    # exact_code: the question depends on an exact code, a good test for hybrid search
    ("exact_code", "What wind speed stops double-deck vehicles crossing exposed bridges under SR-417?", "Gusts over 85 km/h.", [["85"]], ["Double-deck vehicles must stop crossing exposed bridges when gusts exceed 85 km/h."]),
    ("exact_code", "What does SR-444 say about fuel containers?", "Refuse carriage of any fuel container larger than 5 litres.", [["5 litres", "5 liters", "five litres"]], ["Refuse carriage of any fuel container larger than 5 litres."]),
    ("exact_code", "What is the renewal period for TR-305?", "Every 18 months.", [["18 months"]], ["Course TR-305 must be renewed every 18 months."]),
    ("exact_code", "Which form must a driver complete after a collision?", "Form IR-7.", [["IR-7"]], ["The driver must complete form IR-7 before the end of the shift."]),
    ("exact_code", "Who is required to take course TR-410?", "Drivers rostered on Route 27.", [["Route 27"]], ["Course TR-410 is required for: Drivers rostered on Route 27."]),
    # paraphrase: worded differently from the manual
    ("paraphrase", "If I'm ill, how soon before work do I have to tell someone?", "At least 90 minutes before the shift.", [["90 minutes"]], ["no later than 90 minutes before the start of a rostered shift"]),
    ("paraphrase", "How long do you keep things that passengers forget on buses?", "28 days.", [["28 days"]], ["Items left on vehicles are kept at the Central Station lost property office for 28 days."]),
    ("paraphrase", "How long can someone drive before they have to stop for a rest?", "4 hours and 30 minutes.", [["4 hours and 30", "4.5 hours", "4 hours 30", "four and a half"]], ["Drivers may not drive for more than 4 hours and 30 minutes without a break of at least 30 minutes."]),
    ("paraphrase", "What should I do if the battery on an electric bus starts smoking?", "Move at least 75 metres away.", [["75 metres", "75 meters", "75 m"]], ["Move at least 75 metres away from any electric vehicle showing battery smoke."]),
    # rule
    ("rule", "Can a driver use a handheld phone while stopped at a bus stop?", "No, not even when stationary.", [["not", "no,", "cannot", "can't", "may not"]], ["Drivers must not use a handheld phone while in the cab, even when the vehicle is stationary at a stop."]),
    ("rule", "Is a doctor's certificate needed for a 5-day sickness absence?", "No, only for absences longer than 7 calendar days.", [["7 calendar days", "7 days", "seven"]], ["certificate is required for any absence longer than 7 calendar days."]),
    ("rule", "Can an inspector ask for cash on the vehicle for a penalty fare?", "No, they must issue a written notice.", [["written notice"]], ["Inspectors must issue a written notice and must not ask for cash on the vehicle."]),
    ("rule", "Is a 70-year-old passenger charged at 08:00 on a weekday?", "Yes. Free travel starts after 09:30 on weekdays.", [["09:30", "9:30"]], ["Passengers aged 65 or over travel free after 09:30 on weekdays and all day at weekends."]),
    # calculation
    ("calculation", "A grade G4 employee works 4 hours of overtime in a week. How much overtime pay do they get?", "$147.60 (4 x 24.60 x 1.5).", [["147.60", "147.6"]], ["Grade G4 hourly rate: $24.60.", "The first 4 hours of overtime in a week are paid at 1.5 times the hourly rate."]),
    ("calculation", "Two adults and one 10-year-old take a single trip across two zones. What is the total fare?", "$7.75 (3.10 + 3.10 + 1.55).", [["7.75"]], ["A single adult fare across two zones costs $3.10.", "Passengers aged 5 to 15 pay 50% of the adult fare."]),
    ("calculation", "How many passengers in total, seated and standing, can class AT-7C carry?", "125 (51 + 74).", [["125"]], ["Class AT-7C seats 51 passengers and carries up to 74 standing passengers."]),
    # multi_page: the answer needs facts from two distant pages
    ("multi_page", "Who manages the depot that operates Route 14?", "Oluwaseun Adeyemi (Route 14 runs from Marlstone).", [["Adeyemi"]], ["Route 14 runs between Foundry Way and Eastgate Mall and is operated from Marlstone Depot.", "The Marlstone depot manager is Oluwaseun Adeyemi."]),
    ("multi_page", "How often is the vehicle class used on Route 22 inspected?", "Every 22,000 km (Route 22 uses AT-7C).", [["22000", "22,000"]], ["Route 22 is normally worked by class AT-7C vehicles.", "Class AT-7C receives a scheduled inspection every 22000 km."]),
    ("multi_page", "What battery capacity does the vehicle class on Route 27 have?", "560 kWh (Route 27 uses AT-8X).", [["560"]], ["Route 27 is normally worked by class AT-8X vehicles.", "The energy system of class AT-8X is electric, 560 kWh battery."]),
    # superseded: an amendment replaces an earlier value
    ("superseded", "What is the current night premium per hour?", "$3.10 (Amendment 2 replaced the earlier rate).", [["3.10"]], ["The night premium is now $3.10 per hour instead of the earlier rate."]),
    ("superseded", "What is the penalty fare for no valid ticket, under the latest rules?", "$75, or $40 if paid within 14 days (Amendment 3).", [["$75", "75"]], ["The penalty fare for travelling without a valid ticket is now $75"]),
    # not_in_document: several look close to something the manual does contain
    ("not_in_document", "Who manages the Dunmere depot?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "What is the hourly rate for grade G9?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "What is the battery capacity of class AT-9Z?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "How often does Route 99 run at peak times?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "What is the dental insurance allowance?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "What is the fine for smoking on a bus?", "Not in the document.", [["Not in the document"]], []),
    ("not_in_document", "Who is the chief executive of Ashgrove Regional Transit?", "Not in the document.", [["Not in the document"]], []),
]

# must not appear anywhere in the manual, or the not_in_document questions would be wrong
ABSENT = ["Dunmere", "G9", "AT-9Z", "Route 99", "dental", "insurance", "smoking", "chief executive"]


def normalise(text):
    return re.sub(r"\s+", " ", text)


def page_text(blocks):
    return normalise(" ".join(block.lstrip("# ") for block in blocks))


def build_eval(pages):
    texts = [page_text(blocks) for blocks in pages]
    whole = " ".join(texts)
    for word in ABSENT:
        assert not re.search(rf"\b{re.escape(word)}\b", whole, re.IGNORECASE), f"{word} appears in the manual"

    questions = []
    type_counts = {}
    for number, (qtype, question, expected, must_include, evidence) in enumerate(Q, start=1):
        pages_found = set()
        for sentence in evidence:
            hits = [i for i, text in enumerate(texts, start=1) if sentence in text]
            assert len(hits) == 1, (question, sentence, hits)
            pages_found.add(hits[0])
        # hold out roughly 2 in 5 of each type, so settings can't be tuned on them
        seen = type_counts.get(qtype, 0)
        type_counts[qtype] = seen + 1
        questions.append({
            "id": f"atm_q{number:02d}",
            "type": qtype,
            "split": "test" if seen % 5 in (1, 3) else "dev",
            "question": question,
            "expected_answer": expected,
            "must_include": must_include,
            "evidence": evidence,
            "pages": sorted(pages_found),
            "answerable": bool(evidence),
        })
    return {
        "document": "ashgrove_manual.pdf",
        "how_to_grade": (
            "An answer is correct if, for every group in must_include, it contains at least one of the group's strings "
            "(ignoring case). An answer has the right citation if it cites at least one page listed in pages. For questions "
            "with answerable=false, the pages list is empty and there is nothing to cite. Retrieval is right if the retrieved "
            "chunks contain every string in evidence. Tune settings on split=dev only, and report split=test as the score."
        ),
        "questions": questions,
    }


if __name__ == "__main__":
    all_pages = build_pages()
    write_pdf(all_pages, HERE / "ashgrove_manual.pdf")
    data = build_eval(all_pages)
    (HERE / "ashgrove_eval_set.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{len(all_pages)} pages, {len(data['questions'])} questions")
