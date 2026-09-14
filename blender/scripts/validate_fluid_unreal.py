"""Full editor visual and PIE validation. No edits are saved by this script."""
import unreal as u,json,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2] if Path(__file__).parent.name=='scripts' else Path(__file__).parent/'v1_staging'
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
level.load_level('/Game/FluidWorld/Maps/L_AbyssalGarden')
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='CAM_Descent')
u.EditorPythonScripting.set_keep_python_script_alive(True)
level.editor_set_viewport_realtime(True)
level.pilot_level_actor(cam)
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
u.SystemLibrary.execute_console_command(world,'r.ScreenPercentage 100')
u.SystemLibrary.execute_console_command(world,'t.MaxFPS 30')
u.SystemLibrary.execute_console_command(world,'r.HighResScreenshotDelay 64')
state={'stage':0,'started':time.monotonic(),'last':time.monotonic(),'report':{}}
def finish(error=None):
    if error:state['report']['error']=error
    (ROOT/'docs/unreal_validation.json').write_text(json.dumps(state['report'],indent=2))
    u.unregister_slate_post_tick_callback(handle)
    u.SystemLibrary.quit_editor()
def tick(delta):
    try:
        now=time.monotonic();age=now-state['last'];stage=state['stage']
        if now-state['started']>240:finish('Validation timeout');return
        if stage==0 and age>20:
            state['shot']=u.AutomationLibrary.take_high_res_screenshot(1440,810,str(ROOT/'renders/previews/Unreal_V1_Entrance.png'),camera=cam,delay=2.0)
            state['stage']=1;state['last']=now
        elif stage==1 and age>10 and (ROOT/'renders/previews/Unreal_V1_Entrance.png').exists():
            state['report']['screenshot']='Unreal_V1_Entrance.png'
            level.eject_pilot_level_actor()
            level.editor_request_begin_play();state['stage']=2;state['last']=now
        elif stage==2 and age>8:
            game=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
            pawn=u.GameplayStatics.get_player_pawn(game,0)
            assert pawn,'No player pawn spawned in PIE'
            state['pawn']=pawn;state['start']=pawn.get_actor_location()
            state['report']['pawn_class']=pawn.get_class().get_name()
            state['report']['start_cm']=list(state['start'].to_tuple())
            state['stage']=3;state['last']=now
        elif stage==3:
            state['pawn'].add_movement_input(u.Vector(0,-1,0),1,False)
            if age>3:
                end=state['pawn'].get_actor_location();distance=(end-state['start']).length()
                state['report']['movement_distance_cm']=distance
                state['report']['end_cm']=list(end.to_tuple())
                assert distance>100,'Flying movement did not advance the pawn'
                # World collision geometry must also answer actual Unreal traces.
                hit=u.SystemLibrary.line_trace_single(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(),u.Vector(0,0,500),u.Vector(0,0,-1000),u.TraceTypeQuery.ECC_VISIBILITY,True,[],u.DrawDebugTrace.NONE,True)
                state['report']['floor_trace_hit']=bool(hit and hit.to_tuple()[0])
                assert state['report']['floor_trace_hit'],'Floor collision trace failed'
                level.editor_request_end_play();state['stage']=4;state['last']=now
        elif stage==4 and age>4:
            state['report']['status']='passed';finish()
    except Exception:finish(traceback.format_exc())
handle=u.register_slate_post_tick_callback(tick)
