from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from member.utils import is_logged_in, get_user

# Import Models and Serializers
from .models import Restroom

# Import Util Functions
from .utils import (
    log_time_func,
    direction_request_func,
    get_steps_func,
    get_point_coordinate_func,
    find_exit_func,
    coordinate_request_func,
    pedestrian_request_func,
    get_tmap_info_func,
    navigation_response_func,
    get_additional_ETA_func,
)


# Find Route
@api_view(["POST"])
def navigation(request):
    # 로그인 인증
    if not is_logged_in(request):
        return Response(
            {"message": "인증된 사용자가 아닙니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    origin = request.data.get("departure")
    destination = request.data.get("arrival")
    print(f"{log_time_func()} - Navigation: 출발 / 도착 - {origin} / {destination}")

    # T map 경로 요청
    try:
        departure_lon, departure_lat = coordinate_request_func(origin)
        arrival_lon, arrival_lat = coordinate_request_func(destination)

        if not (departure_lon and departure_lat and arrival_lon and arrival_lat):

            message = "경로를 받아올 수 없어요.\n출발지와 도착지를 확인해주세요."

            return Response(
                navigation_response_func(message, 0, False),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # T Map "출발지 - 도착지" 도보 경로 요청
        pedestrian_route = pedestrian_request_func(
            departure_lon,
            departure_lat,
            arrival_lon,
            arrival_lat,
        )

        (
            pedestrian_coordinate_list,
            pedestrian_description_list,
            tmap_duration,
            distance,
        ) = get_tmap_info_func(pedestrian_route)

        # Pedestrain response value init
        pedestrian_polyline_info = list()
        pedestrian_detail_route_info = list()

        pedestrian_polyline_info.append(
            {
                "type": "walk",
                "info": pedestrian_coordinate_list,
            }
        )

        pedestrian_detail_route_info.append(
            {
                "type": "walk",
                "info": pedestrian_description_list,
            }
        )

        message = "경로 탐색에 성공했어요!\n도보 경로를 안내할게요"

        pedestrian_response_value = navigation_response_func(
            message,
            tmap_duration,
            False,
            pedestrian_polyline_info,
            pedestrian_detail_route_info,
        )

    except Exception as err:
        print(f"{log_time_func()} - Navigation: 경로 탐색 FAILED")
        print(f"{log_time_func()} - Navigation: EXCEPTION ERROR: {err}")

        message = "경로를 받아올 수 없어요.\n출발지와 도착지를 확인해주세요."

        return Response(
            navigation_response_func(message, 0, False),
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Google Maps 경로 API Request

    try:
        mode = "transit"  # Options : walking, driving, bicycling, transit
        transit_mode = "subway"

        response_json = direction_request_func(origin, destination, mode, transit_mode)

        # Routes & Steps 데이터
        steps, google_duration = get_steps_func(response_json)

    except:
        pedestrian_response_value["message"] = (
            "대중교통 경로를 받아올 수 없어요.\n도보 경로로 안내합니다."
        )

        return Response(
            pedestrian_response_value,
            status=status.HTTP_200_OK,
        )

    # 도보 경로랑 대중교통 경로 1차 비교

    if tmap_duration <= 15 or abs(google_duration - tmap_duration) <= 5:
        print(f"{log_time_func()} - Navigation: 1차 비교에서 도보가 더 낫다!")
        return Response(
            pedestrian_response_value,
            status=status.HTTP_200_OK,
        )

    # 지하철 있는지 확인

    # Step, travel_mode 리스트 Init
    step_list = list()
    step_travel_mode_list = list()

    # Transit Flags
    is_subway_exist = True  # "SUBWAY" 유무

    # 각 Step 확인 및 저장
    for step in steps:
        travel_mode = step.get("travel_mode")

        # Transit의 Type 확인
        if travel_mode == "TRANSIT":
            transit_type = (
                step.get("transit_details").get("line").get("vehicle").get("type")
            )

            # 경로 상에 버스가 포함된 경우, 종료
            if transit_type == "BUS":
                print(f"{log_time_func()} - Navigation: 경로에 버스 포함")
                is_subway_exist = False

                break

        step_list.append(step)
        step_travel_mode_list.append(travel_mode)

    google_route_pedestrian_departure_duration = int(
        steps[0].get("duration").get("text").rstrip("분")
    )
    google_route_pedestrian_arrival_duration = int(
        steps[-1].get("duration").get("text").rstrip("분")
    )

    # 1) "지하철 x" -> 도보 경로 안내
    if not is_subway_exist:
        print(f"{log_time_func()} - Navigation: 지하철 없음, 도보 경로 안내")

        pedestrian_response_value["message"] = (
            "지하철을 이용하는 경로가 없어요.\n도보 경로를 안내할게요."
        )

        return Response(
            pedestrian_response_value,
            status=status.HTTP_200_OK,
        )

    # 2) "지하철 o" -> 지하철 경로 안내
    else:
        try:
            step_length = len(step_travel_mode_list)

            # 지하철 구간 각 polyline 및 경로 상세 정보 추출
            subway_stops = list()
            cached_subway_stops = list()
            subway_polyline_list = list()
            subway_description_list = list()

            for step_idx in range(0, step_length):

                if step_travel_mode_list[step_idx] != "TRANSIT":
                    continue

                transit_details = step_list[step_idx].get("transit_details")

                departure_station_name = transit_details.get("departure_stop").get(
                    "name"
                )
                arrival_station_name = transit_details.get("arrival_stop").get("name")
                line_name = transit_details.get("line").get("short_name")

                subway_description_list.append(
                    f"{line_name}: {departure_station_name} - {arrival_station_name}"
                )

                line_number = line_name.rstrip("호선")

                departure_station_fullname = f"{departure_station_name} {line_number}"
                subway_stops.append(departure_station_fullname)
                cached_subway_stops.append(f"{departure_station_name} {line_number}")

                subway_polyline_list.append(
                    {
                        "line": line_name,
                        "polyline": step_list[step_idx].get("polyline").get("points"),
                    }
                )

                arrival_station_fullname = f"{arrival_station_name} {line_number}"
                cached_subway_stops.append(f"{arrival_station_name} {line_number}")
                subway_stops.append(arrival_station_fullname)

            user = get_user(request)

            cache.set(user, cached_subway_stops, 3600 * 2)
            print(
                f"{log_time_func()} - Navigation: {user} 의 지하철 경로 REDIS 저장 SUCCESS"
            )

            # 엘레베이터 출구 찾기
            departure_station_elevator_exit = find_exit_func(subway_stops[0])
            arrival_station_elevator_exit = find_exit_func(subway_stops[-1])

            # 두 출구 하나라도 엘레베이터가 없는 경우 => 도보 경로 안내
            if not (departure_station_elevator_exit and arrival_station_elevator_exit):
                print(
                    f"{log_time_func()} - Navigation: {subway_stops[0]} 엘레베이터 출구 {departure_station_elevator_exit}"
                )
                print(
                    f"{log_time_func()} - Navigation: {subway_stops[-1]} 엘레베이터 출구 {arrival_station_elevator_exit}"
                )
                print(f"{log_time_func()} - Navigation: 도보 경로로 대체 안내")

                pedestrian_response_value["message"] = (
                    "지하철 출입구에 엘레베이터가 없어요.\n도보 경로를 안내할게요."
                )

                return Response(
                    pedestrian_response_value,
                    status=status.HTTP_200_OK,
                )

            # 두 엘레베이터 출구의 좌표값, tuple: (lon, lat)
            departure_exit_lon, departure_exit_lat = coordinate_request_func(
                departure_station_elevator_exit
            )
            arrival_exit_lon, arrival_exit_lat = coordinate_request_func(
                arrival_station_elevator_exit
            )

            # 지하철 출입구의 Kakao Maps API 결과 없을 때
            if not (
                departure_exit_lon
                and departure_exit_lat
                and arrival_exit_lon
                and arrival_exit_lat
            ):

                print(
                    f"{log_time_func()} - Navigation: 지하철 출입구 Kakao Maps API 결과 없음, 도보 경로로 대체 안내"
                )

                pedestrian_response_value["message"] = (
                    "지하철 출입구에 엘레베이터가 없어요.\n도보 경로를 안내할게요."
                )

                return Response(
                    pedestrian_response_value,
                    status=status.HTTP_200_OK,
                )

            # Google Maps 경로 API에서 출발, 도착지 좌표 반환
            start_lon, start_lat = get_point_coordinate_func(steps, 1)
            end_lon, end_lat = get_point_coordinate_func(steps, 0)

            # T Map: "출발지 - 승차역 엘레베이터 출구" 도보 경로 요청
            start_pedestrian_route = pedestrian_request_func(
                start_lon,
                start_lat,
                departure_exit_lon,
                departure_exit_lat,
            )

            # T Map: "하차역 엘레베이터 출구 - 도착지" 도보 경로 요청
            end_pedestrian_route = pedestrian_request_func(
                arrival_exit_lon,
                arrival_exit_lat,
                end_lon,
                end_lat,
            )

            (
                departure_pedestrian_coordinate_list,
                departure_pedestrian_description_list,
                departure_pedestrian_duration,
                departure_pedestrian_distance,
            ) = get_tmap_info_func(start_pedestrian_route)
            (
                arrival_pedestrian_coordinate_list,
                arrival_pedestrian_description_list,
                arrival_pedestrian_duration,
                arrival_pedestrian_distance,
            ) = get_tmap_info_func(end_pedestrian_route)

            # 전체 polyline, coordinate 데이터 완성

            # Subway response value init
            subway_polyline_info = list()
            subway_detail_route_info = list()

            subway_polyline_info.append(
                {
                    "type": "walk",
                    "info": departure_pedestrian_coordinate_list,
                }
            )
            subway_polyline_info.append(
                {
                    "type": "subway",
                    "info": subway_polyline_list,
                }
            )
            subway_polyline_info.append(
                {
                    "type": "walk",
                    "info": arrival_pedestrian_coordinate_list,
                }
            )

            # 전체 detail_route_info 완성
            subway_detail_route_info.append(
                {
                    "type": "walk",
                    "info": departure_pedestrian_description_list,
                }
            )
            subway_detail_route_info.append(
                {
                    "type": "subway",
                    "info": subway_description_list,
                }
            )
            subway_detail_route_info.append(
                {
                    "type": "walk",
                    "info": arrival_pedestrian_description_list,
                }
            )

            # Calculate ETA
            additional_ETA = get_additional_ETA_func(
                departure_pedestrian_distance,
                departure_pedestrian_duration,
                arrival_pedestrian_distance,
                arrival_pedestrian_duration,
                subway_stops,
            )

            # 총 시간 계산
            google_duration = (
                google_duration
                + departure_pedestrian_duration
                + arrival_pedestrian_duration
                - google_route_pedestrian_departure_duration
                - google_route_pedestrian_arrival_duration
                + additional_ETA
            )

            print(
                f"{log_time_func()} - Navigation: Additional / Total ETA (min) - {additional_ETA} / {google_duration}"
            )

            message = "경로 탐색에 성공했어요!\n지하철을 이용하는 경로를 안내할게요"

            subway_response_value = navigation_response_func(
                message,
                google_duration,
                is_subway_exist,
                subway_polyline_info,
                subway_detail_route_info,
            )

            print(f"{log_time_func()} - Navigation: 지하철 경로 탐색 SUCCESS")

            return Response(
                subway_response_value,
                status=status.HTTP_200_OK,
            )

        except Exception as err:
            print(
                f"{log_time_func()} - Navigation: 지하철 경로 탐색 FAILED, 도보 경로로 대체 안내"
            )
            print(f"{log_time_func()} - Navigation: EXCEPTION ERROR: {err}")

            pedestrian_response_value["message"] = (
                "지하철을 이용하는 경로가 없어요.\n도보 경로를 안내할게요."
            )

            return Response(
                pedestrian_response_value,
                status=status.HTTP_200_OK,
            )


# Find Restrooms on Current Route
@api_view(["GET"])
def restroom(request):
    # 로그인 인증
    if not is_logged_in(request):
        return Response(
            {"message": "인증된 사용자가 아닙니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user = get_user(request)
        cached_subway_stops = cache.get(user)

        filtered_restrooms = Restroom.objects.filter(
            station_fullname__in=cached_subway_stops
        )

        # 특정 필드만 추출
        restrooms = filtered_restrooms.values(
            "station_fullname",
            "is_outside",
            "floor",
            "restroom_location",
        )

    except:
        print(f"{log_time_func()} - Restroom: 화장실 없음")
        restrooms = []

    if restrooms:
        for restroom in restrooms:
            station_fullname = restroom.get("station_fullname")

            name, line = station_fullname.split()
            name = name if name[-1] == "역" else name + "역 "
            line += "호선"
            station_fullname = name + line

            restroom["station_fullname"] = station_fullname

            longitude, latitude = coordinate_request_func(station_fullname)

            restroom["coordinate"] = {
                "longitude": longitude,
                "latitude": latitude,
            }

        print(f"{log_time_func()} - Restroom: 화장실 탐색 SUCCESS")

        return Response({"restrooms": restrooms})

    else:
        return Response({"restrooms": ""})
