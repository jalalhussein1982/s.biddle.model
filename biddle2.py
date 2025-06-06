import math
import csv

# Epsilon for avoiding division by zero or for float comparisons
EPSILON = 1e-9
MAX_SIMULATION_DAYS = 1000 # Safeguard for maximum simulation duration

def get_float_input(prompt_text, default_value):
    """Gets float input from the user, with a default value."""
    while True:
        try:
            user_input = input(f"{prompt_text} (default: {default_value}): ")
            if not user_input:
                return default_value
            return float(user_input)
        except ValueError:
            print("Invalid input. Please enter a number.")

def run_daily_battle_simulation():
    """
    Runs a day-by-day battle simulation based on Biddle's model and outputs to CSV.
    """
    print("Please provide the input variables for the Biddle Model Daily Simulation.")
    print("Default values are based on Biddle's Appendix (e.g., Table A.1, Fig A.2 column where applicable).\n")

    # --- Input Variables with Defaults ---
    R_in = get_float_input("Invader troop strength (R)", 1250000)
    B_in = get_float_input("Defender troop strength (B)", 1000000)
    YR_in = get_float_input("Invader's mean weapon introduction year (YR) (e.g., 1910)", 1910)
    YB_in = get_float_input("Defender's mean weapon introduction year (YB) (e.g., 1910)", 1910)
    d_in = get_float_input("Depth of defender's forward positions (km) (d)", 15)
    fr_in = get_float_input("Fraction of defender's troops in mobile reserve (fr)", 0.4)
    fe_in = get_float_input("Fraction of defender's forward garrison exposed (fe)", 0.0)
    Vr_in = get_float_input("Velocity of defender's reserve movements (km/day) (Vr)", 100)
    Va_in = get_float_input("Velocity of invader's assault (km/day) (Va)", 4.5)
    wa_in = get_float_input("Invader's assault frontage (km) (wa)", 25)
    wth_in = get_float_input("Theater frontage overall (km) (wth)", 500)

    k1_in = get_float_input("k1 (invaders one defender can halt)", 2.5)
    k2_in = get_float_input("k2 (fit parameter for Ps)", 0.01)
    k3_in = get_float_input("k3 (invaders to pin one defender)", 0.4)
    k4_in = get_float_input("k4 (fit parameter for rho1)", 0.5)
    k5_in = get_float_input("k5 (invader off-axis casualties - campaign total)", 200000)
    k6_in = get_float_input("k6 (defender off-axis casualties - campaign total)", 200000)
    k7_in = get_float_input("k7 (fit parameter for Ca)", 5)
    k8_in = get_float_input("k8 (invader casualties per defender/day at zero Va)", 0.1)
    k9_in = get_float_input("k9 (invader flank defenders required parameter)", 0.01)

    # --- Initial Static Calculations (once at the beginning) ---
    if wth_in <= EPSILON:
        print("Error: Theater frontage (wth) must be positive.")
        return
    if d_in <= EPSILON: # Depth can be very small but should be positive if breakthrough is a concept
        print("Error: Depth of defender's positions (d) must be positive for meaningful breakthrough assessment.")
        # Allow simulation to run if d_in is very small, breakthrough might happen on day 1.
        if d_in <=0: d_in = EPSILON # Ensure positive for logic

    TR_calc = (YR_in - 1900) / 10.0 if YR_in >= 1900 else 0.0
    TB_calc = (YB_in - 1900) / 10.0 if YB_in >= 1900 else 0.0
    if YR_in < 1900: print(f"Warning: YR was < 1900, TR_calc set to {TR_calc}.")
    if YB_in < 1900: print(f"Warning: YB was < 1900, TB_calc set to {TB_calc}.")


    TC_calc = (TB_calc**2) / (TR_calc + EPSILON) if TR_calc > -EPSILON else (TB_calc**2) / EPSILON # Avoid division by zero
    T_rho_calc = (TR_calc**2) / (TB_calc + EPSILON) if TB_calc > -EPSILON else (TR_calc**2) / EPSILON

    exp_ps = -k2_in * Vr_in
    Ps_calc = 0.0
    if TR_calc <= EPSILON : # If TR_calc is 0 or very near
        Ps_calc = 0.0
    else:
        try:
            Ps_val = math.pow(TR_calc, exp_ps)
            Ps_calc = min(max(Ps_val, 0.0), 1.0) # Clamp Ps between 0 and 1
            if Ps_val > 1.0 and TR_calc < 1.0 : # TR between 0 and 1 with negative exponent
                 print(f"Notice: Ps calculated as {Ps_val:.4f} (due to 0 < TR < 1), clamped to {Ps_calc:.4f}.")
            elif Ps_val < 0.0: # Should not happen with TR_calc > 0
                 print(f"Warning: Ps calculated as {Ps_val:.4f}, clamped to {Ps_calc:.4f}.")

        except (ValueError, OverflowError) as e:
            print(f"Warning: Could not calculate Ps due to math error ({e}), Ps_calc set to 0.")
            Ps_calc = 0.0


    H_calc = k1_in * (1 - fe_in)

    rho1_denominator = math.pow(T_rho_calc, k4_in) if T_rho_calc >= 0 else float('nan') # Avoid complex if T_rho_calc < 0
    if math.isnan(rho1_denominator) or abs(rho1_denominator) < EPSILON:
        rho1_calc = float('inf') if (k9_in * B_in * fr_in * Ps_calc) > 0 else 0.0
    else:
        rho1_calc = (k9_in * B_in * fr_in * Ps_calc) / rho1_denominator

    rho2_calc = (k3_in * B_in * (1 - fr_in)) / wth_in

    r0_initial_calc = R_in - rho2_calc * (wth_in - wa_in)
    b0_initial_calc = (B_in * (1 - fr_in) * wa_in) / (wth_in * (d_in if d_in > EPSILON else EPSILON) ) # Use d_in for b0 calc if > 0

    # Ca_static_calc is invader casualties per km gained at PoA
    Ca_static_calc = k7_in * (1 - fe_in) * TC_calc * b0_initial_calc * (Va_in + k8_in)
    if Ca_static_calc < 0: Ca_static_calc = 0 # Casualties cannot be negative

    # delta_r_daily is the daily reduction in invader strength rt (from A.12)
    delta_r_daily_rate = Ca_static_calc * Va_in + 2 * rho1_calc * Va_in
    if delta_r_daily_rate < 0: delta_r_daily_rate = 0 # Rate of loss cannot be negative

    # --- Initialize Daily Simulation Variables ---
    rt_current = r0_initial_calc
    bt_current = b0_initial_calc

    G_cumulative = 0.0
    CR_cumulative_on_axis = 0.0 # On-axis, k5 added at the end
    CB_cumulative_no_k6 = 0.0   # POA and reserves, k6 added at the end

    csv_data_rows = []
    simulation_active = True
    final_campaign_inv_cas = 0
    final_campaign_def_cas = 0

    # --- Daily Simulation Loop ---
    for day in range(1, MAX_SIMULATION_DAYS + 1):
        if not simulation_active:
            break

        rt_sod = rt_current # Invader strength at Start of Day
        bt_sod = bt_current # Defender strength at Start of Day

        # Default values for current day's events
        reinforcements_today_survived = 0.0
        def_cas_reserves_today = 0.0
        km_gained_today = 0.0
        inv_cas_poa_today = 0.0
        def_cas_poa_today = 0.0
        
        halt_condition_met_sod = 1 if rt_sod <= H_calc * bt_sod + EPSILON else 0 # Check halt at SOD

        # If halted at SOD or invader cannot advance, log current state and prepare to stop
        if halt_condition_met_sod == 1 or (Va_in <= EPSILON and day > 0) : # For Va_in=0, allow one record then stop
            simulation_active = False
            # km_gained_today, inv_cas_poa_today, etc., remain 0
            rt_eod = rt_sod # No change if halted or no Va
            bt_eod = bt_sod # No change if halted or no Va
        else:
            # Defender Reinforcement (A.14 logic for bt, and reserve casualties)
            time_for_reserves_to_arrive_fully = (wth_in / Vr_in) if Vr_in > EPSILON else float('inf')
            
            if (day -1) < time_for_reserves_to_arrive_fully : # day-1 represents fully elapsed days
                # Surviving reinforcements arriving today
                reinforcements_today_survived = (B_in * fr_in * Vr_in * Ps_calc) / wth_in
                
                # Casualties among reserves attempting to move today
                # Rate of reserves attempting to move = (B_in * fr_in * Vr_in) / wth_in
                # Fraction suffering casualties = (1 - Ps_calc)
                if Vr_in > EPSILON:
                    reserve_attempt_rate = (B_in * fr_in * Vr_in) / wth_in
                    def_cas_reserves_today = reserve_attempt_rate * (1 - Ps_calc)
                    if def_cas_reserves_today < 0: def_cas_reserves_today = 0
            
            bt_after_reinforcement = bt_sod + reinforcements_today_survived

            # Invader Advance and On-Axis Casualties for the day
            # Advance occurs if not halted AND Va_in > 0
            # The halt condition was checked against bt_sod. If defender reinforces and that *causes* halt,
            # the invader might still get one day of advance against bt_sod.
            # However, rt = H*bt is a general condition for advance. Let's use bt_after_reinforcement for this check.
            # If rt_sod > H_calc * bt_after_reinforcement: # If still superior after defender reinforces
            # No, the halt is rt(attacker) vs bt(defender). If rt_sod <= H_calc * bt_sod, no advance.
            # If rt_sod > H_calc * bt_sod, invader *tries* to advance.
            
            km_gained_today = Va_in # Assumes invader advances if not halted at SOD
            G_cumulative += km_gained_today

            inv_cas_poa_today = Ca_static_calc * km_gained_today
            if inv_cas_poa_today < 0: inv_cas_poa_today = 0
            CR_cumulative_on_axis += inv_cas_poa_today
            
            # Defender Casualties at Point of Attack (based on b0_initial_calc, as per A.21)
            def_cas_poa_today = b0_initial_calc * km_gained_today
            if def_cas_poa_today < 0: def_cas_poa_today = 0

            # Update Invader Strength (rt) for End of Day
            rt_eod = rt_sod - delta_r_daily_rate
            if rt_eod < 0: rt_eod = 0
            
            # Update Defender Strength (bt) for End of Day (only by reinforcement as per A.15)
            bt_eod = bt_after_reinforcement
            
            rt_current = rt_eod # for next iteration
            bt_current = bt_eod # for next iteration


        # Total defender casualties for the day
        def_cas_total_today = def_cas_poa_today + def_cas_reserves_today
        CB_cumulative_no_k6 += def_cas_total_today

        # Breakthrough check
        breakthrough_status_eod = 1 if G_cumulative >= (d_in - EPSILON) else 0
        if breakthrough_status_eod == 1:
            simulation_active = False # Stop after this day

        # If simulation is stopping this day, mark it
        current_simulation_continues_flag = 1 if simulation_active else 0
        
        # Store data for CSV
        row = {
            "Day": day,
            "R_in": R_in, "B_in": B_in, "YR_in": YR_in, "YB_in": YB_in, "d_in": d_in, "fr_in": fr_in,
            "fe_in": fe_in, "Vr_in": Vr_in, "Va_in": Va_in, "wa_in": wa_in, "wth_in": wth_in,
            "k1": k1_in, "k2": k2_in, "k3": k3_in, "k4": k4_in, "k5_Campaign": k5_in,
            "k6_Campaign": k6_in, "k7": k7_in, "k8": k8_in, "k9": k9_in,
            "TR_calc": f"{TR_calc:.2f}", "TB_calc": f"{TB_calc:.2f}", "TC_calc": f"{TC_calc:.2f}",
            "T_rho_calc": f"{T_rho_calc:.2f}", "Ps_calc": f"{Ps_calc:.4f}", "H_calc": f"{H_calc:.2f}",
            "rho1_calc": f"{rho1_calc:.2f}", "rho2_calc": f"{rho2_calc:.2f}",
            "r0_initial_calc": f"{r0_initial_calc:.0f}", "b0_initial_calc": f"{b0_initial_calc:.0f}",
            "Ca_static_calc": f"{Ca_static_calc:.2f}", "delta_r_daily_rate": f"{delta_r_daily_rate:.2f}",
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
            "rt_EOD": f"{rt_eod:.0f}", "bt_EOD": f"{bt_eod:.0f}", # Using rt_eod and bt_eod from this day's calc
            "Breakthrough_Status_EOD (0=No,1=Yes)": breakthrough_status_eod,
            "Halt_Condition_Met_SOD (0=No,1=Yes)": halt_condition_met_sod,
            "Simulation_Continues_Next_Day (0=No,1=Yes)": current_simulation_continues_flag,
            "Final_Campaign_Inv_Cas_Total": "", # Placeholder
            "Final_Campaign_Def_Cas_Total": ""  # Placeholder
        }
        csv_data_rows.append(row)

        if not simulation_active: # If simulation stopped this day
            final_campaign_inv_cas = CR_cumulative_on_axis + k5_in
            final_campaign_def_cas = CB_cumulative_no_k6 + k6_in
            csv_data_rows[-1]["Final_Campaign_Inv_Cas_Total"] = f"{final_campaign_inv_cas:.0f}"
            csv_data_rows[-1]["Final_Campaign_Def_Cas_Total"] = f"{final_campaign_def_cas:.0f}"
            break # Exit loop

    # --- Write to CSV ---
    if not csv_data_rows:
        print("No simulation data generated.")
        return

    csv_file_name = "battle_simulation_daily_log.csv"
    try:
        with open(csv_file_name, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=csv_data_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_data_rows)
        print(f"\nSimulation complete. Daily log saved to '{csv_file_name}'")
        if final_campaign_inv_cas > 0 or final_campaign_def_cas > 0 :
             print(f"Final Campaign Invader Casualties (incl. k5): {final_campaign_inv_cas:.0f}")
             print(f"Final Campaign Defender Casualties (incl. k6): {final_campaign_def_cas:.0f}")

    except IOError:
        print(f"Error: Could not write to CSV file '{csv_file_name}'.")


if __name__ == "__main__":
    run_daily_battle_simulation()
