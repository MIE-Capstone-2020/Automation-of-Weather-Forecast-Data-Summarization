# -*- coding: utf-8 -*-
"""Automation of Weather Forecast Data Summarization Code.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1k4WV6T2SuGB_i55CehuoNoxefok_LUXw

#Library Installation
"""

#@title
! pip install pyproj
! pip install pygrib==2.1.3

! pip install -U geopy
! pip install -U plotly
! pip install geojson

"""#Goolge Drive Access"""

#@title
from google.colab import drive
drive.mount('/content/drive')

"""#Library Imports"""

#@title
import pygrib
import numpy as np
import matplotlib.pyplot as plt
import os
import pandas as pd
import plotly.express as px
import math

from math import cos, asin, sqrt
from matplotlib.colors import ListedColormap
from scipy.ndimage import label

from sklearn.cluster import Birch
from sklearn.cluster import KMeans
from sklearn.cluster import MiniBatchKMeans

from geopy.geocoders import Nominatim
from collections import Counter
import geojson

from shapely.geometry import shape, Point

"""#Solution Functions"""

#@title
def get_data(path, year, month, day, start_time, end_time, verbose = 0):
  '''Get data from the following structure: Day Folder: time_element grib file'''
  file_days = [str(year)+str(month)+str(day)+f"{time:02d}" for time in range(start_time, end_time+1)]
  files_time = []
  for file in os.listdir(path):
    if not file.endswith(".tar"):
      if verbose:
        print(file)
      file_path = os.path.join(path, file) 
      files_element = []
      for file2 in os.listdir(file_path):
        res = [ele for ele in file_days if(ele in file2)]
        if "_001_" in file2 and bool(res):
          files_element.append(os.path.join(file_path, file2))
          if verbose:
            print(file2)
      if files_element:
        files_time.append(files_element)
  return files_time

def get_data2(path, year, month, day, start_time, end_time, verbose = 0):
  '''Get data from the following structure: Day Folder: time_element grib file, specific to test cases for Solution Testing and Validation Section'''
  files_time = []
  file_hours = [str(year)+str(month)+str(day)+"00_" + f"{time:03d}" for time in range(start_time, end_time)]
  for hour in file_hours:
    hour_element = []
    for file in os.listdir(path):
      if hour in file:
        hour_element.append(os.path.join(path, file))
    if hour_element:
      files_time.append(hour_element)
  return files_time

def combine_data(files_time, preview = False):
  '''Data processing and structuring. Final output shape: (W x H x E x T), where W is width, H is height, E is number of elements, T is number of hours in the time period'''
  combined_grib_data_time = None
  combined_grib_data_arrays = []

  for files in files_time:
    
    if preview: 
      fig, axs = plt.subplots(nrows=1, ncols=3, figsize=(18, 6),
                          subplot_kw={'xticks': [], 'yticks': []})
    element = files
    combined_grib_data = None
    if preview: 
      for ax, interp_element in zip(axs.flat, element):
          gribs = pygrib.open(interp_element)
          grib_data, lats, lons = gribs.message(1).data()

          if combined_grib_data is None:
              combined_grib_data = grib_data
          else:
              combined_grib_data = np.ma.dstack((combined_grib_data,grib_data))
          im = ax.imshow(grib_data, cmap='viridis')
          fig.colorbar(im, ax=ax)
          ax.set_title(interp_element.split("/")[-1])
    else: 
      for interp_element in element:
          gribs = pygrib.open(interp_element)
          grib_data, lats, lons = gribs.message(1).data()

          if combined_grib_data is None:
              combined_grib_data = grib_data
          else:
              combined_grib_data = np.ma.dstack((combined_grib_data,grib_data))
    if preview: 
      plt.tight_layout()
      plt.show()
    combined_grib_data_arrays.append(combined_grib_data)
  combined_grib_data_time = np.ma.stack(combined_grib_data_arrays, axis=-1)
  return lats, lons, combined_grib_data_time

def crop_data(combined_grib_data_time, lats, lons, lat_ll, lon_ll, lat_ur, lon_ur, preview = False):
  '''Cropping the data to a specified bounding box using lower left and upper right corners'''
  mask_2d = (np.ma.masked_values((lats > lat_ll) & (lats < lat_ur) & (lons > lon_ll) & (lons < lon_ur), combined_grib_data_time[:,:,0,0]))
  combined_grib_data_time.mask = np.ma.stack([np.ma.stack([~mask_2d]*combined_grib_data_time.shape[2], axis=2)]*combined_grib_data_time.shape[3], axis=3)
  if preview:
    fig, axs = plt.subplots(nrows=2, ncols=3, figsize=(18, 6),
                            subplot_kw={'xticks': [], 'yticks': []})
    for ax, e in zip(axs.flat, range(combined_grib_data_time[:,:,:,0].shape[2])):
        im = ax.imshow(combined_grib_data_time[:,:,e,0], cmap='viridis')
        fig.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.show()

  combined_grib_data = combined_grib_data_time[:,:,:,0]

  row_starts = []
  row_ends = []
  for row in np.ma.notmasked_contiguous(combined_grib_data[:,:,0], axis=1):
      if row:
        for s in row:
          row_starts.append(s.start)
          row_ends.append(s.stop)

  col_starts = []
  col_ends = []
  for col in np.ma.notmasked_contiguous(combined_grib_data[:,:,0], axis=0):
      if col:
        for s in col:
          col_starts.append(s.start)
          col_ends.append(s.stop)

  min_row, min_col = np.min(row_starts), np.min(col_starts)
  max_row, max_col = np.max(row_ends), np.max(col_ends)

  minmaxs = (min_row, min_col, max_row, max_col)

  combined_grib_data_crop = combined_grib_data_time[min_col:max_col+1, min_row:max_row+1, :, :]

  return minmaxs, combined_grib_data_crop

def cluster_data(combined_grib_data_crop, num_clus, minmaxs):
  '''Clustering data using MiniBatchKMeans. The main output is the labels of each point the cropped gribfile'''
  resized_grib_data = combined_grib_data_crop.reshape(-1,combined_grib_data_crop.shape[-1]*combined_grib_data_crop.shape[-2]) #reshape into -1, elements * days (6*2)

  kmeans = MiniBatchKMeans(n_clusters=num_clus, random_state=0, verbose=0).fit(resized_grib_data.filled())
  labels = kmeans.labels_.reshape(combined_grib_data_crop[:,:,0,0].shape)

  min_row, min_col, max_row, max_col = minmaxs

  lons_cropped = lons[min_col:max_col+1, min_row:max_row+1]
  lats_cropped = lats[min_col:max_col+1, min_row:max_row+1]

  llcrnrlon = lons_cropped.min()
  llcrnrlat = lats_cropped.min()
  urcrnrlon = lons_cropped.max()
  urcrnrlat = lats_cropped.max()
  return lats_cropped, lons_cropped, labels

def split_clusters(labels):
  '''Contour lines detection. Clusters that contain two or more non-adjacent groups of data points are separated into smaller clusters and relabelled. The new cluster labels are outputted'''
  values = np.unique(labels.ravel())
  offset = 0
  result = np.zeros_like(labels)
  for v in values:
    labeled, num_features = label(labels == v)
    result += labeled + offset*(labeled > 0)
    offset += num_features
  print(len(np.unique(labels)), "zones split into", len(np.unique(result)), "zones")
  return result

def interactive_map(result, lats_cropped, lons_cropped, topk = 5):
  '''Visualization of labelled clusters. For the purposes of efficiently using Plotly, data statistics were calculated in this function'''
  polygons = []
  df = pd.DataFrame(columns=['zone', 'idx'])
  num_zones_found = len(np.unique(result))

  b = Counter(result.ravel())
  most_common = []
  for cluster, freq in b.most_common(min(topk, num_zones_found)):
    most_common.append(cluster)

  for i in most_common:
    if i == -1:
      continue
    zone = np.ma.masked_where(np.isin(result, [i], invert=True), result)

    polygon_verts = []
    polygon_verts_ends = []

    starts, ends = np.ma.notmasked_edges(zone, axis=1)
    for x, y in zip(starts[0], starts[1]):
        polygon_verts.append((lons_cropped[x,y], lats_cropped[x,y]))

    for x, y in zip(ends[0], ends[1]):
        polygon_verts_ends.append((lons_cropped[x,y], lats_cropped[x,y]))
    
    if polygon_verts:
      polygon_verts.extend(polygon_verts_ends[::-1])
      polygon_verts.extend([polygon_verts[0]])
      geometry = geojson.Polygon([polygon_verts])
      polygon = geojson.Feature(geometry=geometry, id=i)
      polygons.append(polygon)

    locator = Nominatim(user_agent="uoftMIEECCCCapstone2020")
    coordinates = str(np.ma.masked_where(result != i, lats_cropped).mean()) + "," + str(np.ma.masked_where(result != i, lons_cropped).mean())
    location = locator.reverse(coordinates, exactly_one=True, zoom=11)

    TT_array = np.ma.masked_array(combined_grib_data_crop[:,:,0,:], mask=np.ma.stack([zone.mask]*combined_grib_data_crop.shape[-1], axis=2))
    UV_array = np.ma.masked_array(combined_grib_data_crop[:,:,1,:], mask=np.ma.stack([zone.mask]*combined_grib_data_crop.shape[-1], axis=2))
    WD_array = np.ma.masked_array(combined_grib_data_crop[:,:,2,:], mask=np.ma.stack([zone.mask]*combined_grib_data_crop.shape[-1], axis=2))
    
    if TT_array.count() > 0:
      temp = TT_array.mean()-273.15
      temp_min = TT_array.min()-273.15
      temp_max = TT_array.max()-273.15

      temp = np.round(temp,2)
      temp_min = np.round(temp_min,2)
      temp_max = np.round(temp_max,2)

      UV = UV_array.mean()
      UV_min = UV_array.min()
      UV_max = UV_array.max()

      UV = np.round(UV,2)
      UV_min = np.round(UV_min,2)
      UV_max = np.round(UV_max,2)

      WD = WD_array.mean()
      WD_min = WD_array.min()
      WD_max = WD_array.max()

      WD = np.round(WD,2)
      WD_min = np.round(WD_min,2)
      WD_max = np.round(WD_max,2)


      df = df.append({
                      'zone': i,
                      'idx':i,
                      "location": location.address,
                      "Avg TT (C)": temp,
                      "Min TT (C)": temp_min,
                      "Max TT (C)": temp_max,
                      "Avg UV": UV,
                      "Min UV": UV_min,
                      "Max UV": UV_max,
                      "Avg WD": WD,
                      "Min WD": WD_min,
                      "Max WD": WD_max
                      },
                      ignore_index=True)
    

  feat_collection = geojson.FeatureCollection(polygons)

  fig = px.choropleth_mapbox(df, geojson=feat_collection, locations='zone', color='idx',
                            color_continuous_scale="Viridis",
                            range_color=(0, 12),
                            # labels={'idx':'id'},
                            hover_data=["location", "Avg TT (C)", "Min TT (C)", "Max TT (C)", "Avg UV", "Min UV", "Max UV", "Avg WD", "Min WD", "Max WD"],
                            center = {"lat": lats_cropped.mean(), "lon": lons_cropped.mean()},
                            opacity=0.3,
                            )

  fig.update_geos(
      visible=True, resolution=50,
      showcountries=True, countrycolor="RebeccaPurple",
      showland=True,
      showlakes=True
  )

  fig.update_geos(fitbounds="locations")
  fig.update_layout(mapbox_style="open-street-map", showlegend=False)
  fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
  fig.show()

def contains(a_polygon, a_point):
  '''Support function to vectorize the contains() function for performance improvement'''
    return a_polygon.contains(a_point)
contains_vectorized = np.vectorize(contains)

"""# Example Walkthrough
## Variables to fill:


*   num_clusters:
>This is "sensitivity" parameter. The code will find more zones the higher this number is
*   year, month, day, start_time, end_time:
>Specify which date range to use and will differ depending on the file naming structure you have
* path_to_data:
>Enter the path to your data here. This example uses a mounted google drive path
* lat_ll, lon_ll, lat_ur, lon_ur:
> The lower left and upper right corners (in latitude and longitude) of the required bounding box


"""

num_clusters = 30
year = 2019
month = 12
day = 27
start_time = 11
end_time = start_time + 24
path_to_data = "/content/drive/MyDrive/Capstone-2020/Weather Data for Testing/HRDPS Files/Dec 27 HRDPS"


#GTA
lat_ll = 41.622704
lon_ll = -83.322900
lat_ur = 45.400267
lon_ur = -75.827520

files_time = get_data2(path_to_data, year, month, day, start_time, end_time, verbose = 0)
lats, lons, combined_grib_data_time = combine_data(files_time, preview = False)
minmaxs, combined_grib_data_crop = crop_data(combined_grib_data_time, lats, lons, lat_ll, lon_ll, lat_ur, lon_ur, preview = False)
lats_cropped, lons_cropped, labels = cluster_data(combined_grib_data_crop, num_clus=num_clusters, minmaxs=minmaxs)
final_clusters = split_clusters(labels)

"""#Interactive map for entire bounding box
Case: 6AM Dec 27, 2019 to 6AM Dec 28, 2019 on entire bounding box
"""

interactive_map(final_clusters, lats_cropped, lons_cropped, topk=30)

"""# Cropping bounding box to a specified geometery:

Case: 6AM Dec 27, 2019 to 6AM Dec 28, 2019 on CHUM_Radio_footprint
"""

path_to_geometry = "/content/drive/MyDrive/Capstone-2020/GeoJSON Files/CHUM_Radio_footprint_EPSG4326.geojson"

with open(path_to_geometry) as f:
    geometry = geojson.load(f)
polygon = shape(geometry['features'][0]["geometry"])
points = list(np.dstack((lons_cropped, lats_cropped)).reshape(-1,2))
geo_points = pd.DataFrame({'single_column':points}).single_column.apply(lambda x: Point(x[0], x[1])).values
mask = contains_vectorized(polygon, geo_points[:,np.newaxis]).reshape(lons_cropped.shape)
masked_final_clusters = np.where(mask, final_clusters, -1)

interactive_map(masked_final_clusters, lats_cropped, lons_cropped, topk=30)