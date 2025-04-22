from enum import Enum

class Privacy(Enum):
    PUBLIC = 0
    PRIVATE = 1

class TerminType(Enum):
    MEETUP = 1
    CONFERENCE = 2
    CLASS = 3
    TRAINING = 4
    APPOINTMENT = 10
    MEETING = 11
    EXAM = 12
    HEARING = 13
    INTERVIEW = 14

    def __str__(self):
        return self.name
    
class CultureType(Enum):
    MOVIE = 1
    CONCERT = 2
    SPORTS = 3
    MUSEUM = 4
    ENTERTAINMENT = 5

    def __str__(self):
        return self.name
    
class SocialType(Enum):
    DINNER = 1
    WEDDING = 2
    FUNERAL = 3
    PARTY = 4
    GATHERING = 5

    def __str__(self):
        return self.name

class AwayType(Enum):
    HOTEL = 1
    TRIP = 2
    BNB = 3
    COUCH = 4
    RESORT = 5

    def __str__(self):
        return self.name

class TransportType(Enum):
    BUS = 1
    TRAIN = 2
    FLIGHT = 3
    FERRY = 4
    CAR = 5

    def __str__(self):
        return self.name

all_event_names = set(TerminType._member_names_) \
                    .union(set(CultureType._member_names_)) \
                    .union(set(SocialType._member_names_)) \
                    .union(set(AwayType._member_names_)) \
                    .union(set(TransportType._member_names_))
