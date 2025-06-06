import math
import csv
import itertools
from typing import List  # using custom float_range instead of numpy

# Epsilon for avoiding division by zero or for float comparisons
EPSILON = 1e-9
MAX_SIMULATION_DAYS = 1000 # Safeguard for maximum simulation duration


def float_range(start: float, end: float, step: float) -> List[float]:
    values = []
    if step > 0:
        while start <= end + EPSILON:
            values.append(start)
            start += step
    else:
        while start >= end - EPSILON:
            values.append(start)
            start += step
    return values

def get_variable_values_from_user(prompt_text, default_single_value_str):
    """
    Gets variable values from the user.
    User can enter a single value, or 'start,end,step'.
    Returns a list of float values.
    """
    while True:
        try:
            user_input_str = input(f"{prompt_text} (default: '{default_single_value_str}'; or enter 'start,end,step'): ")
            if not user_input_str:
                user_input_str = default_single_value_str

            parts = [part.strip() for part in user_input_str.split(',')]
            
            if len(parts) == 1:
                return [float(parts[0])]
            elif len(parts) == 3:
                start, end, step = float(parts[0]), float(parts[1]), float(parts[2])
                if step == 0:
                    print("Step cannot be zero. Please re-enter.")
                    continue
                # Use float_range for robust float stepping
                # Add a small epsilon to 'end' if step is positive to include 'end' if it's a multiple of step
                # Subtract a small epsilon if step is negative
                if step > 0:
                    values = float_range(start, end + EPSILON, step)
                else: # step < 0
                    values = float_range(start, end - EPSILON, step)
                
                if not values: # If arange results in empty list (e.g. start=10, end=5, step=1)
                    print(f"Warning: Range {start},{end},{step} generated no values. Using start value: [{start}]")
                    return [start]
                return [round(v, 6) for v in values] # Round to avoid excessive float precision issues
            else:
                print("Invalid input format. Enter a single number or 'start,end,step'.")
        except ValueError:
            print("Invalid number format. Please re-enter.")
        except Exception as e:
            print(f"An error occurred: {e}. Please re-enter.")

def simulate_one_scenario(scenario_id, inputs):
    """
    Simulates one battle scenario based on the provided inputs.
    Returns:
        - daily_log_for_scenario (list of dicts): Log for each day.
        - final_outcomes_for_scenario (dict): Summary of the scenario.
    """
    # Unpack inputs from the dictionary
    R_in = inputs["R_in"]
    B_in = inputs["B_in"]
    YR_in = inputs["YR_in"]
    YB_in = inputs["YB_in"]
    d_in = inputs["d_in"]
    fr_in = inputs["fr_in"]
    fe_in = inputs["fe_in"]
    Vr_in = inputs["Vr_in"]
    Va_in = inputs["Va_in"]
    wa_in = inputs["wa_in"]
    wth_in = inputs["wth_in"]
    k1_in = inputs["k1_in"]
    k2_in = inputs["k2_in"]
    k3_in = inputs["k3_in"]
    k4_in = inputs["k4_in"]
    k5_in = inputs["k5_in"]
    k6_in = inputs["k6_in"]
    k7_in = inputs["k7_in"]
    k8_in = inputs["k8_in"]
    k9_in = inputs["k9_in"]

    # --- Initial Static Calculations ---
    # (Same as before, but using unpacked inputs)
    if wth_in <= EPSILON: wth_in = EPSILON # Avoid division by zero, ensure positive
    if d_in <= 0: d_in = EPSILON # Depth must be positive for breakthrough logic

    TR_calc = (YR_in - 1900) / 10.0 if YR_in >= 1900 else 0.0
    TB_calc = (YB_in - 1900) / 10.0 if YB_in >= 1900 else 0.0

    TC_calc = (TB_calc**2) / (TR_calc + EPSILON) if TR_calc > -EPSILON else (TB_calc**2) / EPSILON
    T_rho_calc = (TR_calc**2) / (TB_calc + EPSILON) if TB_calc > -EPSILON else (TR_calc**2) / EPSILON

    exp_ps = -k2_in * Vr_in
    Ps_calc = 0.0
    if TR_calc <= EPSILON:
        Ps_calc = 0.0
    else:
        try:
            Ps_val = math.pow(TR_calc, exp_ps)
            Ps_calc = min(max(Ps_val, 0.0), 1.0)
        except (ValueError, OverflowError):
            Ps_calc = 0.0
    
    H_calc = k1_in * (1 - fe_in)

    rho1_denominator = math.pow(T_rho_calc, k4_in) if T_rho_calc >= 0 else float('nan')
    if math.isnan(rho1_denominator) or abs(rho1_denominator) < EPSILON:
        rho1_calc = float('inf') if (k9_in * B_in * fr_in * Ps_calc) > 0 else 0.0
    else:
        rho1_calc = (k9_in * B_in * fr_in * Ps_calc) / rho1_denominator
    if rho1_calc == float('inf') and Va_in > EPSILON: # If infinite flank guards needed and advancing, delta_r becomes inf
        pass # This will likely lead to immediate halt if r0 is finite

    rho2_calc = (k3_in * B_in * (1 - fr_in)) / wth_in
    r0_initial_calc = R_in - rho2_calc * (wth_in - wa_in)
    b0_initial_calc = (B_in * (1 - fr_in) * wa_in) / (wth_in * d_in)

    Ca_static_calc = k7_in * (1 - fe_in) * TC_calc * b0_initial_calc * (Va_in + k8_in)
    if Ca_static_calc < 0: Ca_static_calc = 0

    delta_r_daily_rate = Ca_static_calc * Va_in + 2 * rho1_calc * Va_in
    if delta_r_daily_rate < 0: delta_r_daily_rate = 0
    if delta_r_daily_rate == float('inf'): # If flank guard requirements are infinite
        pass # rt will likely go to 0 or negative very quickly

    # --- Initialize Daily Simulation Variables ---
    rt_current = r0_initial_calc
    bt_current = b0_initial_calc
    if rt_current < 0: rt_current = 0 # Initial strength cannot be negative

    G_cumulative = 0.0
    CR_cumulative_on_axis = 0.0
    CB_cumulative_no_k6 = 0.0

    daily_log_for_scenario = []
    simulation_active = True
    breakthrough_occurred_flag = 0
    halt_occurred_this_scenario_flag = 0
    final_day_of_simulation = 0

    # --- Daily Simulation Loop ---
    for day in range(1, MAX_SIMULATION_DAYS + 1):
        final_day_of_simulation = day
        if not simulation_active:
            final_day_of_simulation = day -1 # It stopped on the previous day's EOD
            break

        rt_sod = rt_current
        bt_sod = bt_current

        reinforcements_today_survived = 0.0
        def_cas_reserves_today = 0.0
        km_gained_today = 0.0
        inv_cas_poa_today = 0.0
        def_cas_poa_today = 0.0
        
        halt_condition_met_sod = 1 if rt_sod <= H_calc * bt_sod + EPSILON or rt_sod < EPSILON else 0

        if halt_condition_met_sod == 1 or (Va_in <= EPSILON and day > 0) or delta_r_daily_rate == float('inf'):
            simulation_active = False
            if halt_condition_met_sod == 1 and breakthrough_occurred_flag == 0 : # Only set halt if no breakthrough
                 halt_occurred_this_scenario_flag = 1
            rt_eod = rt_sod
            bt_eod = bt_sod
        else:
            time_for_reserves_to_arrive_fully = (wth_in / Vr_in) if Vr_in > EPSILON else float('inf')
            
            if (day - 1) < time_for_reserves_to_arrive_fully:
                reinforcements_today_survived = (B_in * fr_in * Vr_in * Ps_calc) / wth_in
                if Vr_in > EPSILON:
                    reserve_attempt_rate = (B_in * fr_in * Vr_in) / wth_in
                    def_cas_reserves_today = reserve_attempt_rate * (1 - Ps_calc)
                    if def_cas_reserves_today < 0: def_cas_reserves_today = 0
            
            bt_after_reinforcement = bt_sod + reinforcements_today_survived
            
            km_gained_today = Va_in
            G_cumulative += km_gained_today

            inv_cas_poa_today = Ca_static_calc * km_gained_today
            if inv_cas_poa_today < 0: inv_cas_poa_today = 0
            CR_cumulative_on_axis += inv_cas_poa_today
            
            def_cas_poa_today = b0_initial_calc * km_gained_today # Based on initial defender density at PoA
            if def_cas_poa_today < 0: def_cas_poa_today = 0

            rt_eod = rt_sod - delta_r_daily_rate
            if rt_eod < 0: rt_eod = 0
            
            bt_eod = bt_after_reinforcement
            
            rt_current = rt_eod
            bt_current = bt_eod

        def_cas_total_today = def_cas_poa_today + def_cas_reserves_today
        CB_cumulative_no_k6 += def_cas_total_today

        current_breakthrough_status_eod = 1 if G_cumulative >= (d_in - EPSILON) else 0
        if current_breakthrough_status_eod == 1:
            breakthrough_occurred_flag = 1
            simulation_active = False
            halt_occurred_this_scenario_flag = 0 # Breakthrough overrides halt

        current_simulation_continues_flag = 1 if simulation_active else 0
        
        daily_row = {
            "Scenario_ID": scenario_id, "Day": day,
            # Inputs for this scenario
            "R_in": R_in, "B_in": B_in, "YR_in": YR_in, "YB_in": YB_in, "d_in": inputs["d_in"], "fr_in": fr_in,
            "fe_in": fe_in, "Vr_in": Vr_in, "Va_in": Va_in, "wa_in": wa_in, "wth_in": inputs["wth_in"],
            "k1": k1_in, "k2": k2_in, "k3": k3_in, "k4": k4_in, "k5_Campaign": k5_in,
            "k6_Campaign": k6_in, "k7": k7_in, "k8": k8_in, "k9": k9_in,
            # Static calculations
            "TR_calc": f"{TR_calc:.2f}", "TB_calc": f"{TB_calc:.2f}", "TC_calc": f"{TC_calc:.2f}",
            "T_rho_calc": f"{T_rho_calc:.2f}", "Ps_calc": f"{Ps_calc:.4f}", "H_calc": f"{H_calc:.2f}",
            "rho1_calc": f"{rho1_calc:.2f}", "rho2_calc": f"{rho2_calc:.2f}",
            "r0_initial_calc": f"{r0_initial_calc:.0f}", "b0_initial_calc": f"{b0_initial_calc:.0f}",
            "Ca_static_calc": f"{Ca_static_calc:.2f}", "delta_r_daily_rate": f"{delta_r_daily_rate:.2f}",
            # Daily dynamics
            "rt_SOD": f"{rt_sod:.0f}", "bt_SOD": f"{bt_sod:.0f}",
            "Reinforcements_Today_Survived": f"{reinforcements_today_survived:.0f}",
            "Km_Gained_Today": f"{km_gained_today:.2f}",
            "Km_Gained_Cumulative": f"{G_cumulative:.2f}",
            "Inv_Cas_POA_Today": f"{inv_cas_poa_today:.0f}",
            "Inv_Cas_POA_Cumulative_OnAxis": f"{CR_cumulative_on_axis:.0f}",
            "Def_Cas_POA_Today": f"{def_cas_poa_today:.0f}",
            "Def_Cas_Reserves_Today": f"{def_cas_reserves_today:.0f}",
            "Def_Cas_Total_Today": f"{def_cas_total_today:.0f}",
            "Def_Cas_Cumulative_no_k6": f"{CB_cumulative_no_k6:.0f}",
            "rt_EOD": f"{rt_eod:.0f}", "bt_EOD": f"{bt_eod:.0f}",
            "Halt_Condition_Met_SOD (0=No,1=Yes)": halt_condition_met_sod,
            "Simulation_Continues_Next_Day (0=No,1=Yes)": current_simulation_continues_flag
        }
        daily_log_for_scenario.append(daily_row)

        if not simulation_active:
            break
    
    if day == MAX_SIMULATION_DAYS and simulation_active: # Reached max days without other stop condition
        final_day_of_simulation = MAX_SIMULATION_DAYS
        if breakthrough_occurred_flag == 0 and halt_occurred_this_scenario_flag == 0: # If not halted or breakthrough by max days
            # Consider if it was implicitly halted if rt <= H*bt at MAX_SIM_DAYS EOD
            if rt_current <= H_calc * bt_current + EPSILON or rt_current < EPSILON:
                halt_occurred_this_scenario_flag = 1


    final_outcomes = {
        "Scenario_ID": scenario_id,
        # Inputs
        "R_in": R_in, "B_in": B_in, "YR_in": YR_in, "YB_in": YB_in, "d_in": inputs["d_in"], "fr_in": fr_in,
        "fe_in": fe_in, "Vr_in": Vr_in, "Va_in": Va_in, "wa_in": wa_in, "wth_in": inputs["wth_in"],
        "k1": k1_in, "k2": k2_in, "k3": k3_in, "k4": k4_in, "k5_Campaign": k5_in,
        "k6_Campaign": k6_in, "k7": k7_in, "k8": k8_in, "k9": k9_in,
        # Final Outcomes
        "Final_Campaign_Duration_Days": final_day_of_simulation,
        "Final_Km_Gained_Cumulative": f"{G_cumulative:.2f}",
        "Final_Inv_Cas_POA_Cumulative_OnAxis": f"{CR_cumulative_on_axis:.0f}",
        "Final_Def_Cas_Cumulative_no_k6": f"{CB_cumulative_no_k6:.0f}",
        "Final_Campaign_Inv_Cas_Total": f"{CR_cumulative_on_axis + k5_in:.0f}",
        "Final_Campaign_Def_Cas_Total": f"{CB_cumulative_no_k6 + k6_in:.0f}",
        "Breakthrough_Occurred (0=No,1=Yes)": breakthrough_occurred_flag,
        "Halt_Occurred (0=No,1=Yes)": halt_occurred_this_scenario_flag
    }
    return daily_log_for_scenario, final_outcomes

def main():
    print("Biddle Model Multi-Scenario Simulation Tool")
    print("-------------------------------------------\n")
    
    input_variable_definitions = {
        "R_in": ("Invader troop strength (R)", "1250000"),
        "B_in": ("Defender troop strength (B)", "1000000"),
        "YR_in": ("Invader's mean weapon introduction year (YR)", "1910"),
        "YB_in": ("Defender's mean weapon introduction year (YB)", "1910"),
        "d_in": ("Depth of defender's forward positions (km) (d)", "15"),
        "fr_in": ("Fraction of defender's troops in mobile reserve (fr)", "0.4"),
        "fe_in": ("Fraction of defender's forward garrison exposed (fe)", "0.0"),
        "Vr_in": ("Velocity of defender's reserve movements (km/day) (Vr)", "100"),
        "Va_in": ("Velocity of invader's assault (km/day) (Va)", "4.5"),
        "wa_in": ("Invader's assault frontage (km) (wa)", "25"),
        "wth_in": ("Theater frontage overall (km) (wth)", "500"),
        "k1_in": ("k1 (invaders one defender can halt)", "2.5"),
        "k2_in": ("k2 (fit parameter for Ps)", "0.01"),
        "k3_in": ("k3 (invaders to pin one defender)", "0.4"),
        "k4_in": ("k4 (fit parameter for rho1)", "0.5"),
        "k5_in": ("k5 (invader off-axis casualties - campaign total)", "200000"),
        "k6_in": ("k6 (defender off-axis casualties - campaign total)", "200000"),
        "k7_in": ("k7 (fit parameter for Ca)", "5"),
        "k8_in": ("k8 (invader casualties per defender/day at zero Va)", "0.1"),
        "k9_in": ("k9 (invader flank defenders required parameter)", "0.01"),
    }

    scenario_value_lists = []
    variable_names_in_order = list(input_variable_definitions.keys())

    print("Define input values for each variable. Enter a single number, or 'start,end,step'.\n")
    for var_name in variable_names_in_order:
        prompt, default_val_str = input_variable_definitions[var_name]
        values = get_variable_values_from_user(f"{var_name} - {prompt}", default_val_str)
        scenario_value_lists.append(values)

    # Generate all scenario combinations
    all_scenario_combinations = list(itertools.product(*scenario_value_lists))
    num_scenarios = len(all_scenario_combinations)
    print(f"\nTotal number of scenarios to simulate: {num_scenarios}")
    
    if num_scenarios == 0:
        print("No scenarios generated. Exiting.")
        return
    if num_scenarios > 10000: # A soft warning
        confirm = input(f"Warning: {num_scenarios} is a large number of scenarios and may take a long time. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Simulation cancelled by user.")
            return

    all_scenarios_daily_logs = []
    all_scenarios_final_outcomes = []

    print("\nStarting simulations...")
    for i, scenario_values in enumerate(all_scenario_combinations):
        scenario_id = i + 1
        # Create a dictionary for the current scenario's inputs
        current_scenario_inputs = dict(zip(variable_names_in_order, scenario_values))
        
        print(f"Simulating Scenario {scenario_id}/{num_scenarios}...")
        
        daily_log, final_outcomes = simulate_one_scenario(scenario_id, current_scenario_inputs)
        
        all_scenarios_daily_logs.extend(daily_log)
        all_scenarios_final_outcomes.append(final_outcomes)
        print(f"Scenario {scenario_id} complete. Duration: {final_outcomes['Final_Campaign_Duration_Days']} days, Breakthrough: {'Yes' if final_outcomes['Breakthrough_Occurred (0=No,1=Yes)'] else 'No'}, Halt: {'Yes' if final_outcomes['Halt_Occurred (0=No,1=Yes)'] else 'No'}")


    # --- Write to CSV files ---
    daily_log_csv_name = "battle_simulation_daily_log_SCENARIOS.csv"
    final_outcomes_csv_name = "battle_simulation_final_outcomes_SCENARIOS.csv"

    if all_scenarios_daily_logs:
        try:
            with open(daily_log_csv_name, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=all_scenarios_daily_logs[0].keys())
                writer.writeheader()
                writer.writerows(all_scenarios_daily_logs)
            print(f"\nDaily logs for all scenarios saved to '{daily_log_csv_name}'")
        except IOError:
            print(f"Error: Could not write daily logs to CSV file '{daily_log_csv_name}'.")
        except IndexError:
             print(f"No daily log data to write for '{daily_log_csv_name}'.")


    if all_scenarios_final_outcomes:
        try:
            with open(final_outcomes_csv_name, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=all_scenarios_final_outcomes[0].keys())
                writer.writeheader()
                writer.writerows(all_scenarios_final_outcomes)
            print(f"Final outcomes for all scenarios saved to '{final_outcomes_csv_name}'")
        except IOError:
            print(f"Error: Could not write final outcomes to CSV file '{final_outcomes_csv_name}'.")
        except IndexError:
            print(f"No final outcome data to write for '{final_outcomes_csv_name}'.")
            
    print("\nAll simulations complete.")

if __name__ == "__main__":
    main()
