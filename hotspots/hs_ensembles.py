#from __future__ import print_function, division
from hotspots.result import Results
from hotspots.hs_utilities import Helper
from hotspots.grid_extension import Grid, _GridEnsemble
from ccdc.protein import Protein
import numpy as np

class EnsembleResult(Helper):
    """
    Class that handles the creation and manipulation of ensemble maps from a list of hotspot results.
    """

    class Settings():
        """
        Class that allows for the adjustment of the various Ensemble map parameters. 
        """
        def __init__(self, polar_freq_threshold=20.0, apolar_freq_threshold=0.0, combine_mode="median"):
            """
            Frequency: ((number of times score observed at point)/ (number of maps in ensemble))*100
            For the polar maps, using a frequency threshold is used to remove artefacts of the alignment and "noisy"
            hotspots that are unlikely to contribute to the binding.
            
            For the apolar maps, the default frequency threshold is 0 (meaning to take into account all points), as these 
            effects affect them less due to their larger volume and lack of orientation dependence.
            
            To calculate the ensemble maps, the algorithm takes the median (or mean, or max)of the nonzero values for each point in the polar maps 
            that passes the frequency threshold. For the apolar maps, the default is to take the median of all values.
            
            The combine_mode parameter controls how the information at each point is combined. Currently, the default is to take the
            median (with some modifications for the polar maps), but the 'mean' and 'max' modes could also be useful for
            exploratory work. 
            
            Note: Ensemble maps have not been tested with the positive and negative probes, although the option has been 
            included here to allow exploration and testing.
            
            :param polar_freq_threshold: Minimum frequency of values at a point for that point to be included in the polar ensemble maps
            :type: float
            
            :param apolar_freq_threshold: Minimum frequency of values at a point for that point to be included in the apolar ensemble maps
            :type: float
            
            :param combine_mode: "median", "mean", or maximum
            :type str
            """
            self.polar_frequency_threshold = polar_freq_threshold
            self.apolar_frequency_threshold =  apolar_freq_threshold
            self.combine_mode = combine_mode

    def __init__(self,  hs_results_list, ensemble_id = 'protein', reference_structure=None, settings=None):
        """
        :param ensemble_id: An identifier for the ensemble (e.g. name of the protein)
        
        :param hs_results_list: list of  hotspots results. The protein models used to calculate the maps should be aligned 
                                prior to the hotspots calculation
        :type list
        
        
        """
        # Use default settings if no settings have been provided.
        if settings is None:
            self.settings = self.Settings()
        else:
            self.settings = settings

        self.ensemble_id = ensemble_id
        self.hotspot_results = hs_results_list
        self.grid_ensembles = {}
        self.ensemble_maps = {}
        self.reference_pdb = reference_structure
        self.ensemble_hotspot_result = None


        # Holds information about which maps belong to which protein. Important for downstream analysis.
        self.index_dict = {i: hs.protein.identifier for i, hs, in enumerate(self.hotspot_results)}

    @staticmethod
    def shrink_to_binding_site(in_grid, new_origin, new_far_corner):
        """
        Given an input grid, will reduce it to the area defined by the new origin and far corner
        :param in_grid: a ccdc.utilities.Grid
        :param new_origin: numpy array((x, y, z))
        :param new_far_corner: numpy array((x, y, z))
        :return: ccdc.utilities.Grid
        """
        # Check that the new coordinates fall within the grid:
        ori = np.array(in_grid.bounding_box[0])
        far_c = np.array(in_grid.bounding_box[1])

        if (new_origin > ori).all() and (new_far_corner < far_c).all():
            ori_idxs = in_grid.point_to_indices(tuple(new_origin))
            far_idxs = in_grid.point_to_indices(tuple(new_far_corner))
            region = ori_idxs + far_idxs
            # Get only the sub-grid defined by the 6 indices in region
            new_g = in_grid.sub_grid(region)
            return new_g

        else:
            print("Selected area larger than grid; try reducing the padding in shrink_hotspots()")
            # TODO: Log as error

    def make_ensemble_maps(self, save_grid_ensembles=True):
        """
        Creates summary maps for the ensemble based on the settings provided.
        :return: 
        """
        probes_list = ['donor', 'acceptor', 'apolar', 'positive', 'negative']
        polar_probes = ['donor', 'acceptor', 'positive', 'negative']
        apolar_probes = ['apolar']


        for probe in probes_list:
            ge = _GridEnsemble()
            try:
                probe_grids = [hs.super_grids[probe] for hs in self.hotspot_results]
                ge.make_ensemble_array(probe_grids)

                if save_grid_ensembles:
                    self.grid_ensembles[probe] = ge

                if probe in polar_probes:
                    if self.settings.combine_mode == 'median':
                        ens_grid = ge.as_grid(ge.get_median_frequency_map(threshold=self.settings.polar_frequency_threshold))

                    #The mean and max modes don't currently take into account the frequency
                    elif self.settings.combine_mode in ['mean', 'max']:
                        ens_grid = ge.make_summary_grid(mode=self.settings.combine_mode)

                    else:
                        print('Unrecognised mode for combining grids in {} {}: {}'.format(self.ensemble_id, probe, self.settings.combine_mode))
                        continue

                elif probe in apolar_probes:
                    ens_grid = ge.make_summary_grid(mode=self.settings.combine_mode)

                else:
                    print("Probe type {} in ensemble {} not recognised as polar or apolar".format(probe, self.ensemble_id))
                    continue

                print(probe, ens_grid.nsteps)

                self.ensemble_maps[probe] = ens_grid

            # In case of no charged probes
            except KeyError:
                continue

        self.ensemble_hotspot_result = Results(super_grids=self.ensemble_maps,
                                             protein=self.hotspot_results[0].protein,
                                             buriedness=None,
                                             pharmacophore=False)



class SelectivityResult(Helper):
    """
    Given two hotspots results, subtracts the maps and performs post-processing
    """
    class Settings():
        """
        Settings for the selectivity maps
        """
        def __init__(self, minimal_cluster_score=10.0, cluster_distance_cutoff=1.5,  apolar_percentile_threshold=95.0, polar_percentile_threshold=0.0, minimum_points_cluster_polar=7, minimum_points_cluster_apolar=27):
            """
            :param minimal_cluster_score: the minimal score needed for a cluster to be considered selective
            :type: float 
            
            :param cluster_distance_cutoff: How far away a selective cluster can be from another selective cluster in the off-target map (in angstroms). Some dependence on flexibility of binding site.
                                            Usually between 1.5 and 3.0
            
            :param apolar_percentile_threshold: If specified, only takes the top percentile of points specified in the difference map. Useful for clustering 
                                                in the apolar maps, as they tend to be densely populated with low-scoring values
            :type float:
            
            
            :param polar_percentile_threshold: If specified, only takes the top percentile of points specified in the difference map. Currently not used.
            :type float:
            
            
            :param minimum_points_cluster_polar: Currently, HDBSCAN used for feature detection in the difference maps. This parameter corresponds to
                                                the "min_cluster_size" kwarg. Default value is 7 based on retrospective examples, but 5-10 range could be reasonable.
            :type int:
                                                
            :param minimum_points_cluster_apolar: The apolar maps tend to have larger clusters, so the minimum HDBSCAN cluster size is correspondingly larger.
            :type int:
            """
            self.minimal_cluster_score = minimal_cluster_score
            self.cluster_distance_cutoff = cluster_distance_cutoff
            self.apolar_percentile_threshold = apolar_percentile_threshold
            self.polar_percentile_threshold = polar_percentile_threshold
            self.min_points_cluster_polar = minimum_points_cluster_polar
            self.min_points_cluster_apolar = minimum_points_cluster_apolar

    def __init__(self, target_result, other_result, settings=None):
        """
        :param target_result: hotspots result (may come from an ensemble) for on-target protein
        :param other_result: hotspots result (may come from ensemble) for off-target protein
        """
        if settings is None:
            self.settings = self.Settings()
        else:
            self.settings = settings

        self.target = target_result
        self.off_target = other_result
        self.selectivity_maps = {}
        self.off_target_maps = None
        self.selectivity_result = None
        self.common_grid_dimensions = None
        self.common_grid_nsteps = None


    @staticmethod
    def remove_cluster(map, clust_num):
        """
        Removes a particular cluster from an array (assumes array values are the cluster labels). Note: this currently 
        acts on the array itself, not a copy
        
        :param map: a numpy array, with points labelled by cluster
        :param clust_num: 
        :type int
        
        :return: the numpy array object, with that specific cluster removed
        """
        map[map == clust_num] = 0.0
        return map

    def get_clusters_center_mass(self, dmap, clust_map):
        """
        
        :param self: 
        :param dmap: the difference map
        :param clust_map: numpy array, labelled by cluster
        :return: 
        """
        coords = {}
        for c in set(clust_map[clust_map > 0]):
            arr = dmap * (clust_map == c)
            coords[c] = _GridEnsemble.get_center_of_mass(arr)
        return coords

    def make_difference_maps(self):
        """
        Brings the two results to the same size and subtracts them.
        TODO - think about cases of results with different numbers of probe grids (charged vs not)
        :return: ccdc grids
        """
        diff_maps = {}

        for probe, gr in self.target.super_grids.items():

            try:
                off_gr = self.off_target.super_grids[probe]
            # In case the off-target hotspot result doesn't have a map for that probe
            except KeyError:
                continue

            if gr.check_same_size_and_coords(off_gr):
                c_gr = gr
                c_off = off_gr
            else:
                print("Input grids of different size. Converting to same coordinates.")
                c_gr, c_off = Grid.common_grid([gr, off_gr])

            diff_maps[probe] = _GridEnsemble.array_from_grid(c_gr - c_off)

        self.common_grid_dimensions = np.array(c_gr.bounding_box)
        self.common_grid_nsteps = c_gr.nsteps

        return diff_maps

    def make_selectivity_maps(self):
        """
        Creates the selectivity maps for the polar and apolar probes. 
        :return: 
        """
        diff_maps = self.make_difference_maps()

        probes_list = ['donor', 'acceptor', 'apolar', 'positive', 'negative']
        polar_probes = ['donor', 'acceptor', 'positive', 'negative']
        apolar_probes = ['apolar']

        for probe in probes_list:
            try:
                dmap = diff_maps[probe]

                if probe in polar_probes:
                    # Find the percentile threshold, if specified
                    perc = np.percentile(dmap[dmap>0], self.settings.polar_percentile_threshold)

                    # Find clusters in the target and off-target maps
                    clust_map_on = _GridEnsemble.HDBSCAN_cluster(dmap * (dmap > perc), min_cluster_size=self.settings.min_points_cluster_polar)
                    clust_map_off = _GridEnsemble.HDBSCAN_cluster(dmap * (dmap < - perc), min_cluster_size=self.settings.min_points_cluster_polar)

                elif probe in apolar_probes:
                    # Find the percentile threshold, if specified
                    perc = np.percentile(dmap[dmap > 0], self.settings.apolar_percentile_threshold)

                    # Find clusters in the target and off-target maps
                    clust_map_on = _GridEnsemble.HDBSCAN_cluster(dmap * (dmap > perc),
                                                                 min_cluster_size=self.settings.min_points_cluster_apolar, allow_single_cluster=True)
                    clust_map_off = _GridEnsemble.HDBSCAN_cluster(dmap * (dmap < -perc),
                                                                  min_cluster_size=self.settings.min_points_cluster_apolar, allow_single_cluster=True)

                else:
                    print("Probe type {} not recognised as polar or apolar".format(probe))
                    continue


                #Get the center of mass coordinates for the target and off-target
                coords = self.get_clusters_center_mass(dmap, clust_map_on)
                minus_coords = self.get_clusters_center_mass(dmap, clust_map_off)

                for k in coords.keys():
                    for i in minus_coords.keys():
                        dist = self.get_distance(coords[k], minus_coords[i]) * 0.5
                        # print("Plus clust: {}, minus_clust: {}, distance: {}".format(k, i, dist))
                        if dist < self.settings.cluster_distance_cutoff:
                            self.remove_cluster(clust_map_on, k)
                            self.remove_cluster(clust_map_off, i)

                # Remove any clusters that don't make the medmian cutoff
                for c in set(clust_map_on[clust_map_on > 0]):
                    med = np.median(dmap[clust_map_on == c])

                    if med < self.settings.minimal_cluster_score:
                        self.remove_cluster(clust_map_on, c)

                for c in set(clust_map_off[clust_map_off > 0]):
                    min_med = np.median(dmap[clust_map_off == c])

                    if min_med > -self.settings.minimal_cluster_score:
                        self.remove_cluster(clust_map_off, c)

                ge = _GridEnsemble(dimensions=self.common_grid_dimensions,
                                   shape=self.common_grid_nsteps)

                self.selectivity_maps[probe] = ge.as_grid((clust_map_on>0)*dmap)

            except KeyError:
                continue

        self.selectivity_result = Results(super_grids= self.selectivity_maps,
                                          protein=self.target.protein)











