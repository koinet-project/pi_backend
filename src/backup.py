async def login_queue_worker():
    while True:
        try:
            item = login_queue.get_nowait()
            print(f"Processing user: {item.mac_address} {item.ip_address}")

            timeout_left = datetime.now()
            stop_event = asyncio.Event()

            # Define timer
            async def _timer():
                nonlocal item

                end_time = timeout_left + timedelta(seconds=timeout_duration)

                int p

                while True:
                    now = datetime.now()
                    remaining = (end_time - now).total_seconds()

                    if remaining <= 0:
                        break

                    try:
                        await item.websocket.send_json(
                            {
                                "status": "receiving", 
                                "data": {
                                    "timer": int(remaining),
                                    "coin_count": arduino.coinCount,
                                }
                            }
                        )
                    except Exception as e:
                        print(f"WebSocket closed or failed for {item.mac_address}: {e}")
                        return  # Exit the timer early if the socket is closed


                    time.sleep(1)

                stop_event.set()

            try:
                timeout_left = datetime.now()
                asyncio.create_task(_timer())
                await stop_event.wait()  # Wait for timeout before continuing
            except Exception as e:
                print(f"An error occurred during login for {item.mac_address}: {e}")
                # Optionally send error response
            else:
                if (coin_count == 0):
                    print("Queue finished. No coin is accepted")
                    await item.websocket.send_json({"status": "denied", "reason": "no coin"})
                else:
                    time_minutes = coin_count * 30
                    mikrotik_api.addHotspotUser(item.mac_address, item.ip_address, time_minutes)
                    await item.websocket.send_json({"status": "approved", "time_minutes": time_minutes})

            # Finish queue. Broadcast positions to other
            await broadcast_positions()
            login_queue.task_done()
            print(f"Finished processing login queue for user {item.mac_address} {item.ip_address}")
        except Empty:
            pass
        
        item.done.set()
        await asyncio.sleep(1) 